/**
 * Fix Executor v0.4 - Closed-loop auto-fix with risk classification
 *
 * low_risk  → execute → validate → rollback on failure → report
 * high_risk → generate suggestion → write to pending-actions.md
 */

const fs = require('fs').promises;
const path = require('path');
const { classifyTasks } = require('./lib/classifier');
const { validateConfig, healthCheck, backupFile, rollbackFile } = require('./lib/validator');

const FIXES_HISTORY_PATH = path.join(__dirname, 'fixes-history.json');
const WORKSPACE = path.join(require('os').homedir(), '.openclaw', 'workspace');
const PENDING_ACTIONS_PATH = path.join(WORKSPACE, 'pending-actions.md');

/**
 * Execute fix tasks (v0.4 entry point)
 * @param {Array} tasks - Fix tasks from fixer
 * @param {Object} options - { dryRun: bool, autoApprove: bool }
 * @returns {Object} Execution results
 */
async function executeFixes(tasks, options = {}) {
  const { dryRun = true, autoApprove = false } = options;

  console.log(`\n🔧 Fix Executor v0.4${dryRun ? ' (DRY RUN)' : ''}\n`);

  // Classify tasks by risk level
  const { lowRisk, highRisk } = classifyTasks(tasks);

  console.log(`📊 Classification: ${lowRisk.length} low-risk, ${highRisk.length} high-risk\n`);

  const results = {
    total: tasks.length,
    executed: 0,
    succeeded: 0,
    failed: 0,
    skipped: 0,
    pendingHuman: highRisk.length,
    fixes: [],
  };

  // ── Low-risk: auto-execute ───────────────────────────────────────────────
  for (const task of lowRisk) {
    console.log(`\n📋 [LOW RISK] ${task.id}`);
    console.log(`   Type: ${task.type} | Priority: ${task.priority}`);
    console.log(`   ${task.description}`);

    if (dryRun) {
      console.log(`   ⚠️  DRY RUN - would auto-execute`);
      results.skipped++;
      continue;
    }

    if (!autoApprove) {
      console.log(`   ⏸️  Manual approval required (use --auto-approve to skip)`);
      results.skipped++;
      continue;
    }

    const fixResult = await executeLowRiskTask(task);
    results.fixes.push(fixResult);
    results.executed++;

    if (fixResult.status === 'success') {
      results.succeeded++;
      console.log(`   ✅ Fix succeeded`);
    } else {
      results.failed++;
      const rolled = fixResult.rolledBack ? ' (rolled back)' : '';
      console.log(`   ❌ Fix failed${rolled}: ${fixResult.error}`);
    }
  }

  // ── High-risk: write to pending-actions.md ───────────────────────────────
  if (highRisk.length > 0) {
    console.log(`\n⚠️  High-risk tasks (${highRisk.length}) → pending-actions.md`);
    await writePendingActions(highRisk);
    for (const task of highRisk) {
      console.log(`   📌 ${task.type}: ${task.description}`);
    }
  }

  // Save history
  await saveFixesHistory(results.fixes);

  return results;
}

/**
 * Execute a single low-risk task with validation + rollback
 */
async function executeLowRiskTask(task) {
  const startTime = Date.now();

  try {
    const fixPrompt = buildFixPrompt(task);

    // --- workspace_file / missing_file: no restart needed ---
    if (['workspace_file', 'missing_file', 'cron_prompt'].includes(task.type)) {
      return {
        taskId: task.id,
        type: task.type,
        priority: task.priority,
        riskLevel: 'low_risk',
        status: 'pending_agent',
        prompt: fixPrompt,
        startTime,
        endTime: Date.now(),
        error: null,
        note: 'Prompt generated. Execute via sessions_spawn in loop mode.',
      };
    }

    // --- config: validate → restart → health check ---
    if (task.type === 'config') {
      const configPath = task.strategy?.configPath;
      if (!configPath) {
        throw new Error('task.strategy.configPath is required for config type');
      }

      const backupPath = await backupFile(configPath);

      // Apply the change (strategy provides the new content or a patch)
      if (task.strategy?.newContent) {
        await fs.writeFile(configPath, task.strategy.newContent, 'utf8');
      } else {
        throw new Error('task.strategy.newContent required for config fix');
      }

      // Validate
      const validation = await validateConfig();
      if (!validation.valid) {
        await rollbackFile(configPath, backupPath);
        throw new Error(`Config invalid after fix, rolled back: ${validation.errors.join(', ')}`);
      }

      // Health check (don't restart for every config change; let caller decide)
      const health = await healthCheck();
      if (!health.healthy) {
        await rollbackFile(configPath, backupPath);
        throw new Error(`Health check failed, rolled back: ${health.details}`);
      }

      return {
        taskId: task.id, type: task.type, priority: task.priority,
        riskLevel: 'low_risk', status: 'success', backupPath,
        startTime, endTime: Date.now(), error: null, rolledBack: false,
      };
    }

    // Fallback: generate prompt for agent
    return {
      taskId: task.id, type: task.type, priority: task.priority,
      riskLevel: 'low_risk', status: 'pending_agent', prompt: fixPrompt,
      startTime, endTime: Date.now(), error: null,
    };

  } catch (err) {
    return {
      taskId: task.id, type: task.type, priority: task.priority,
      riskLevel: 'low_risk', status: 'failed', rolledBack: err.message?.includes('rolled back') ?? false,
      startTime, endTime: Date.now(), error: err.message,
    };
  }
}

/**
 * Write high-risk tasks to pending-actions.md
 */
async function writePendingActions(tasks) {
  const now = new Date().toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' });

  let existing = '';
  try {
    existing = await fs.readFile(PENDING_ACTIONS_PATH, 'utf8');
  } catch (_) {}

  const newSection = tasks.map(t => {
    const steps = t.strategy?.action?.steps || [];
    return [
      `### [${t.priority.toUpperCase()}] ${t.type}: ${t.description}`,
      `- **風險等級**: high_risk（需人工確認）`,
      `- **建議操作**:`,
      ...steps.map(s => `  - ${s}`),
      '',
    ].join('\n');
  }).join('\n');

  const header = `## 待確認操作 (${now})\n\n`;
  const content = header + newSection + '\n---\n\n' + existing;

  await fs.writeFile(PENDING_ACTIONS_PATH, content, 'utf8');
}

/**
 * Build fix prompt for sessions_spawn
 */
function buildFixPrompt(task) {
  const { type, description, strategy } = task;
  const steps = strategy?.action?.steps || [];

  return [
    `# Auto-Fix Task: ${type}`,
    '',
    `**Problem:** ${description}`,
    '',
    '**Action Plan:**',
    ...steps.map((s, i) => `${i + 1}. ${s}`),
    '',
    '**Instructions:**',
    '- Follow the action plan step by step',
    '- Document what you did',
    '- If you encounter issues, explain what went wrong',
    '- Commit any file changes to git',
  ].join('\n');
}

/**
 * Save fix history
 */
async function saveFixesHistory(fixes) {
  if (fixes.length === 0) return;

  let history = [];
  try {
    const data = await fs.readFile(FIXES_HISTORY_PATH, 'utf8');
    history = JSON.parse(data);
  } catch (_) {}

  history.push({ timestamp: new Date().toISOString(), fixes });
  if (history.length > 100) history = history.slice(-100);

  await fs.writeFile(FIXES_HISTORY_PATH, JSON.stringify(history, null, 2));
}

/**
 * Load fix history
 */
async function loadFixesHistory() {
  try {
    const data = await fs.readFile(FIXES_HISTORY_PATH, 'utf8');
    return JSON.parse(data);
  } catch (_) {
    return [];
  }
}

module.exports = { executeFixes, loadFixesHistory };

#!/usr/bin/env node

/**
 * Self-Evolution Skill
 * Entry point
 */

const { main: analyze } = require('./analyze');
const { generateFixTasks } = require('./lib/fixer');
const { executeFixes, loadFixesHistory } = require('./fix');
const fs = require('fs').promises;
const path = require('path');

const COMMANDS = {
  analyze: {
    desc: 'Analyze recent sessions for errors and patterns',
    fn: analyze,
  },
  fix: {
    desc: 'Run full evolution cycle (analyze → generate fixes → execute)',
    fn: runFixCycle,
  },
  loop: {
    desc: 'Closed-loop: analyze → classify → auto-fix low-risk → report high-risk',
    fn: runLoop,
  },
  history: {
    desc: 'Show fix execution history',
    fn: showHistory,
  },
};

async function runFixCycle() {
  console.log('🧬 Self-Evolution Cycle Starting\n');
  
  // Parse command-line options
  const args = process.argv.slice(3); // Skip 'node index.js fix'
  const dryRun = !args.includes('--execute');
  const autoApprove = args.includes('--auto-approve');
  
  if (dryRun) {
    console.log('⚠️  DRY RUN MODE (use --execute to actually run fixes)');
  }
  if (!autoApprove && !dryRun) {
    console.log('⏸️  Manual approval required (use --auto-approve to skip)\n');
  }
  
  // Step 1: Analyze
  console.log('📊 Step 1: Analyzing sessions...\n');
  await analyze();
  
  // Step 2: Load analysis results
  const reportPath = path.join(__dirname, 'analysis-report.md');
  let reportText;
  try {
    reportText = await fs.readFile(reportPath, 'utf8');
  } catch (error) {
    console.error('❌ Failed to load analysis report');
    return;
  }
  
  // Step 3: Parse recommendations from report
  // For now, we'll need to re-run the analysis to get structured data
  // TODO: Save analysis results as JSON for easier processing
  console.log('\n🔍 Step 2: Parsing recommendations...\n');
  
  // Mock recommendations for testing
  // In production, this would come from analyzer output
  const recommendations = extractRecommendationsFromReport(reportText);
  
  if (recommendations.length === 0) {
    console.log('✨ No issues found - nothing to fix!');
    return;
  }
  
  console.log(`Found ${recommendations.length} recommendations`);
  
  // Step 4: Generate fix tasks
  console.log('\n🛠️  Step 3: Generating fix tasks...\n');
  const fixTasks = generateFixTasks(recommendations);
  
  if (fixTasks.length === 0) {
    console.log('No automated fixes available for these issues');
    return;
  }
  
  console.log(`Generated ${fixTasks.length} fix tasks`);
  
  // Step 5: Execute fixes
  console.log('\n⚡ Step 4: Executing fixes...\n');
  const results = await executeFixes(fixTasks, { dryRun, autoApprove });
  
  // Step 6: Summary
  console.log('\n📈 Summary:');
  console.log(`   Total tasks: ${results.total}`);
  console.log(`   Executed: ${results.executed}`);
  console.log(`   Succeeded: ${results.succeeded}`);
  console.log(`   Failed: ${results.failed}`);
  console.log(`   Skipped: ${results.skipped}`);
  
  if (dryRun) {
    console.log('\n💡 Run with --execute to apply fixes');
  }
}

/**
 * Extract recommendations from markdown report
 * TODO: Save analysis results as JSON instead
 */
function extractRecommendationsFromReport(reportText) {
  // This is a temporary parser
  // In Phase 3.1, we'll save structured JSON output from analyzer
  const recommendations = [];
  
  // Look for error patterns that we can fix
  const toolErrorMatch = reportText.match(/### tool_error \((\d+) occurrences\)/);
  if (toolErrorMatch && parseInt(toolErrorMatch[1]) >= 3) {
    recommendations.push({
      type: 'repeated_failure',
      priority: 'high',
      description: `tool_error occurred ${toolErrorMatch[1]} times`,
      pattern: {
        count: parseInt(toolErrorMatch[1]),
        errors: [{ type: 'tool_error', message: reportText }]
      }
    });
  }
  
  return recommendations;
}

/**
 * Closed-loop cycle (v0.4):
 * analyze → classify → auto-fix low-risk → report high-risk to pending-actions.md
 */
async function runLoop() {
  const args = process.argv.slice(3);
  const dryRun = args.includes('--dry-run');

  console.log(`\n🔄 Self-Evolution Loop v0.4${dryRun ? ' (DRY RUN)' : ''}\n`);

  // Step 1: Analyze
  console.log('📊 Step 1: Analyzing sessions...\n');
  await analyze();

  // Step 2: Load report
  const reportPath = path.join(__dirname, 'analysis-report.md');
  let reportText;
  try {
    reportText = await fs.readFile(reportPath, 'utf8');
  } catch (_) {
    console.error('❌ Failed to load analysis report');
    return;
  }

  // Step 3: Extract recommendations
  const recommendations = extractRecommendationsFromReport(reportText);
  if (recommendations.length === 0) {
    console.log('\n✨ No issues found — system is healthy!');
    return;
  }
  console.log(`\n🔍 Step 2: Found ${recommendations.length} recommendations`);

  // Step 4: Generate fix tasks
  const fixTasks = generateFixTasks(recommendations);
  if (fixTasks.length === 0) {
    console.log('   No automated fixes available');
    return;
  }

  // Step 5: Execute with classification (auto-approve low-risk)
  console.log(`\n⚡ Step 3: Executing fixes (low-risk auto, high-risk → pending)...\n`);
  const results = await executeFixes(fixTasks, {
    dryRun,
    autoApprove: !dryRun,
  });

  // Step 6: Summary
  console.log('\n📈 Loop Summary:');
  console.log(`   Total tasks    : ${results.total}`);
  console.log(`   Auto-executed  : ${results.executed}`);
  console.log(`   ✅ Succeeded   : ${results.succeeded}`);
  console.log(`   ❌ Failed      : ${results.failed}`);
  console.log(`   📌 High-risk   : ${results.pendingHuman} (written to pending-actions.md)`);

  if (dryRun) {
    console.log('\n💡 Run without --dry-run to apply fixes');
  } else if (results.pendingHuman > 0) {
    console.log('\n⚠️  Check pending-actions.md for tasks that need manual review');
  }
}

/**
 * Show fix execution history
 */
async function showHistory() {
  console.log('📜 Fix Execution History\n');
  
  const history = await loadFixesHistory();
  
  if (history.length === 0) {
    console.log('No fixes executed yet');
    return;
  }
  
  for (const run of history.slice(-10)) { // Show last 10
    console.log(`\n🕐 ${run.timestamp}`);
    console.log(`   Fixes: ${run.fixes.length}`);
    
    for (const fix of run.fixes) {
      const statusIcon = fix.status === 'success' ? '✅' : '❌';
      const duration = fix.endTime - fix.startTime;
      console.log(`   ${statusIcon} ${fix.type} (${duration}ms)`);
      if (fix.error) {
        console.log(`      Error: ${fix.error}`);
      }
    }
  }
}

function printHelp() {
  console.log('Self-Evolution Skill v0.4.0\n');
  console.log('Usage: node index.js [command] [options]\n');
  console.log('Commands:');
  for (const [name, { desc }] of Object.entries(COMMANDS)) {
    console.log(`  ${name.padEnd(12)} ${desc}`);
  }
  console.log('\nOptions for "fix" command:');
  console.log('  --execute       Actually execute fixes (default: dry-run)');
  console.log('  --auto-approve  Skip manual approval for each fix');
  console.log('\nOptions for "loop" command:');
  console.log('  --dry-run       Show plan only, do not execute');
  console.log('');
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === 'help' || command === '--help') {
    printHelp();
    return;
  }

  const cmd = COMMANDS[command];
  if (!cmd) {
    console.error(`Unknown command: ${command}\n`);
    printHelp();
    process.exit(1);
  }

  await cmd.fn();
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { main };

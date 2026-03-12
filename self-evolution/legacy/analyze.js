#!/usr/bin/env node

/**
 * Analyzer Module
 * 分析 OpenClaw sessions 並找出問題
 */

const fs = require('fs');
const path = require('path');
const { scanForErrors, analyzePatterns } = require('./lib/scanner');
const { detectRepeatedErrors, detectToolOveruse, generateRecommendations } = require('./lib/patterns');

/**
 * 讀取 session transcript
 * @param {string} sessionKey - Session key (e.g., 'agent:main:main')
 * @returns {string|null} Transcript 內容
 */
function readSessionTranscript(sessionKey) {
  try {
    const homeDir = require('os').homedir();
    const agentDir = path.join(homeDir, '.openclaw/agents/main/sessions');
    
    // 找到對應的 session 檔案
    const files = fs.readdirSync(agentDir);
    const sessionFile = files.find(f => f.endsWith('.jsonl'));
    
    if (!sessionFile) {
      console.error('No session file found');
      return null;
    }

    const filePath = path.join(agentDir, sessionFile);
    return fs.readFileSync(filePath, 'utf-8');
  } catch (error) {
    console.error('Error reading session:', error.message);
    return null;
  }
}

/**
 * 生成報告
 * @param {Object} stats - 統計結果
 * @param {Array} repeatedErrors - 重複錯誤
 * @param {Object} toolStats - 工具統計
 * @param {Array} recommendations - 建議清單
 * @returns {string} Markdown 格式報告
 */
function generateReport(stats, repeatedErrors, toolStats, recommendations) {
  let report = '# Self-Evolution Analysis Report\n\n';
  report += `Generated: ${new Date().toISOString()}\n\n`;
  
  // Error Summary
  report += '## Error Summary\n\n';

  const sortedTypes = Object.entries(stats)
    .sort((a, b) => b[1].count - a[1].count);

  if (sortedTypes.length === 0) {
    report += 'No errors detected in recent sessions. ✅\n\n';
  } else {
    for (const [type, data] of sortedTypes) {
      report += `### ${type} (${data.count} occurrences)\n\n`;
      
      for (const example of data.examples) {
        report += `- **Tool:** ${example.tool || 'N/A'}\n`;
        report += `  **Error:** ${example.error}\n\n`;
      }
    }
  }

  // Repeated Patterns
  if (repeatedErrors.length > 0) {
    report += '## Repeated Patterns ⚠️\n\n';
    report += 'These issues occurred 3+ times and should be addressed:\n\n';
    
    for (const pattern of repeatedErrors) {
      report += `- **${pattern.type}** (${pattern.tool || 'unknown'}): ${pattern.count} times\n`;
    }
    report += '\n';
  }

  // Tool Usage
  report += '## Tool Usage Statistics\n\n';
  const topTools = Object.entries(toolStats)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);
  
  if (topTools.length > 0) {
    for (const [tool, count] of topTools) {
      report += `- **${tool}**: ${count} calls\n`;
    }
  } else {
    report += 'No tool usage data available.\n';
  }
  report += '\n';

  // Recommendations
  if (recommendations.length > 0) {
    report += '## Recommendations\n\n';
    
    const highPriority = recommendations.filter(r => r.priority === 'high');
    const mediumPriority = recommendations.filter(r => r.priority === 'medium');
    const lowPriority = recommendations.filter(r => r.priority === 'low');
    
    if (highPriority.length > 0) {
      report += '### High Priority 🔴\n\n';
      for (const rec of highPriority) {
        report += `**${rec.issue}**\n`;
        report += `→ ${rec.suggestion}\n\n`;
      }
    }
    
    if (mediumPriority.length > 0) {
      report += '### Medium Priority 🟡\n\n';
      for (const rec of mediumPriority) {
        report += `**${rec.issue}**\n`;
        report += `→ ${rec.suggestion}\n\n`;
      }
    }
    
    if (lowPriority.length > 0) {
      report += '### Low Priority 🟢\n\n';
      for (const rec of lowPriority) {
        report += `**${rec.issue}**\n`;
        report += `→ ${rec.suggestion}\n\n`;
      }
    }
  }

  return report;
}

/**
 * 主函數
 */
async function main() {
  console.log('🔍 Self-Evolution Analyzer v0.2.0\n');

  // 讀取主 session
  console.log('Reading session transcript...');
  const transcript = readSessionTranscript('agent:main:main');
  
  if (!transcript) {
    console.error('❌ Failed to read session');
    process.exit(1);
  }

  console.log(`✅ Loaded ${transcript.split('\n').length} lines\n`);

  // 掃描錯誤
  console.log('Scanning for errors...');
  const errors = scanForErrors(transcript);
  console.log(`Found ${errors.length} potential issues\n`);

  // 分析模式
  console.log('Analyzing patterns...');
  const stats = analyzePatterns(errors);
  
  // 偵測重複錯誤
  console.log('Detecting repeated patterns...');
  const repeatedErrors = detectRepeatedErrors(errors);
  console.log(`Found ${repeatedErrors.length} repeated patterns\n`);
  
  // 分析工具使用
  console.log('Analyzing tool usage...');
  const toolStats = detectToolOveruse(transcript);
  
  // 生成建議
  console.log('Generating recommendations...');
  const recommendations = generateRecommendations(repeatedErrors, toolStats);
  console.log(`Generated ${recommendations.length} recommendations\n`);
  
  // 生成報告
  const report = generateReport(stats, repeatedErrors, toolStats, recommendations);
  
  // 輸出報告
  const reportPath = path.join(__dirname, 'analysis-report.md');
  fs.writeFileSync(reportPath, report);
  
  console.log('📊 Report generated:\n');
  console.log(report);
  console.log(`\n💾 Saved to: ${reportPath}`);
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { main };

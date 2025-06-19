import { useState, useEffect, useRef } from 'react';
import { Terminal, RefreshCw, Play, Square, Clock, CheckCircle, XCircle, FileText, ChevronUp, ChevronDown, BarChart, PieChart } from 'lucide-react';
// Card component not used but preserved for future use
// import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { TestResultsModal } from '../ui/TestResultsModal';
import { testService, TestExecution, TestStreamMessage, TestType } from '../../services/testService';
import { useToast } from '../../contexts/ToastContext';
import { motion, AnimatePresence } from 'framer-motion';
import { useTerminalScroll } from '../../hooks/useTerminalScroll';

interface TestResult {
  name: string;
  status: 'running' | 'passed' | 'failed' | 'skipped';
  duration?: number;
  error?: string;
}

interface CoverageData {
  file: string;
  statements: number;
  branches: number;
  functions: number;
  lines: number;
  uncoveredLines?: string;
}

interface TestExecutionState {
  execution?: TestExecution;
  logs: string[];
  isRunning: boolean;
  duration?: number;
  exitCode?: number;
  // Pretty mode data
  results: TestResult[];
  // Separate summaries for files and tests
  fileSummary?: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
  };
  testSummary?: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
  };
  errorCount?: number;
  startTime?: string;
  // Coverage data
  coverage?: {
    summary: {
      statements: { value: number; total: number };
      branches: { value: number; total: number };
      functions: { value: number; total: number };
      lines: { value: number; total: number };
    };
    files: CoverageData[];
  };
}

export const TestStatus = () => {
  const [displayMode, setDisplayMode] = useState<'pretty'>('pretty');
  const [mcpErrorsExpanded, setMcpErrorsExpanded] = useState(false);
  const [uiErrorsExpanded, setUiErrorsExpanded] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(true); // Start collapsed by default
  const [showTestResultsModal, setShowTestResultsModal] = useState(false);
  const [hasResults, setHasResults] = useState(false);
  
  const [mcpTest, setMcpTest] = useState<TestExecutionState>({
    logs: ['> Ready to run Python tests...'],
    isRunning: false,
    results: []
  });
  
  const [uiTest, setUiTest] = useState<TestExecutionState>({
    logs: ['> Ready to run React UI tests...'],
    isRunning: false,
    results: []
  });

  // Use terminal scroll hooks
  const mcpTerminalRef = useTerminalScroll([mcpTest.logs], !isCollapsed);
  const uiTerminalRef = useTerminalScroll([uiTest.logs], !isCollapsed);

  // WebSocket cleanup functions
  const wsCleanupRefs = useRef<Map<string, () => void>>(new Map());
  const { showToast } = useToast();

  // Cleanup WebSocket connections on unmount
  useEffect(() => {
    return () => {
      wsCleanupRefs.current.forEach((cleanup) => cleanup());
      testService.disconnectAllStreams();
    };
  }, []);

  // Check for test results availability
  useEffect(() => {
    const checkResults = async () => {
      const hasTestResults = await testService.hasTestResults();
      setHasResults(hasTestResults);
    };
    checkResults();
  }, []);

  // Check for results when UI tests complete
  useEffect(() => {
    if (!uiTest.isRunning && uiTest.exitCode === 0) {
      // Small delay to ensure files are written
      setTimeout(async () => {
        const hasTestResults = await testService.hasTestResults();
        setHasResults(hasTestResults);
      }, 2000);
    }
  }, [uiTest.isRunning, uiTest.exitCode]);

  const updateTestState = (
    testType: TestType,
    updater: (prev: TestExecutionState) => TestExecutionState
  ) => {
    switch (testType) {
      case 'mcp':
        setMcpTest(updater);
        break;
      case 'ui':
        setUiTest(updater);
        break;
    }
  };

  const parseTestOutput = (log: string): TestResult | null => {
    // Handle default reporter output - look for test file results
    // Default reporter shows: " ✓ src/App.test.tsx (3 tests | 1 skipped) 10ms"
    // Or failing: " ❯ test/example.test.ts (5 tests | 2 failed) 123ms"
    // Or all pass: " ✓ test/utils.test.ts (10 tests) 50ms"
    
    // Match test file lines with pass/fail/skip status
    const fileMatch = log.match(/^\s*(✓|❯|⚠|×)\s+(.+?\.(?:ts|tsx|js|jsx))\s+\((\d+)\s+tests?(?:\s*\|\s*(\d+)\s+(failed|skipped))?\)\s*(\d+(\.\d+)?)\s*m?s?/);
    if (fileMatch) {
      const [, symbol, filename, totalTests, count, type, duration] = fileMatch;
      let status: 'passed' | 'failed' | 'skipped' = 'passed';
      
      if (symbol === '❯' || symbol === '×' || type === 'failed') {
        status = 'failed';
      } else if (symbol === '⚠' || type === 'skipped') {
        status = 'skipped';
      }
      
      console.log('[PARSE SUCCESS] Test file:', { filename, status, totalTests, failedCount: count });
      return { 
        name: filename, 
        status,
        duration: duration ? parseFloat(duration) / 1000 : undefined
      };
    }
    
    // Handle "FAIL" lines that show failed test details
    // Example: " FAIL  test/example.test.ts > test suite > test name"
    if (log.trim().startsWith('FAIL ')) {
      const failMatch = log.match(/FAIL\s+(.+?)\s+>\s+(.+)/);
      if (failMatch) {
        const [, file, testPath] = failMatch;
        console.log('[PARSE] Failed test:', file, testPath);
        // Don't create a result for individual test failures, just log
        return null;
      }
    }
    
    // Handle running state
    if (log.includes('RUN ') && log.includes('v')) {
      console.log('[PARSE] Test run starting');
      return null;
    }
    
    return null;
  };

  const parseCoverageTable = (logs: string[]): CoverageData[] => {
    const coverageData: CoverageData[] = [];
    let inCoverageTable = false;
    
    for (const line of logs) {
      // Start of coverage table
      if (line.includes('File') && line.includes('% Stmts') && line.includes('% Branch')) {
        inCoverageTable = true;
        continue;
      }
      
      // End of coverage table
      if (inCoverageTable && (line.includes('---') || line.includes('===') || line.trim() === '')) {
        continue;
      }
      
      if (inCoverageTable && line.includes('All files')) {
        inCoverageTable = false;
        continue;
      }
      
      // Parse coverage line
      if (inCoverageTable) {
        // Match lines like: "  api.ts           |     100 |    94.73 |     100 |     100 | 107,109"
        const match = line.match(/^\s*(.+?)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(.*)$/);
        if (match) {
          const [, file, stmts, branch, funcs, lines, uncovered] = match;
          coverageData.push({
            file: file.trim(),
            statements: parseFloat(stmts),
            branches: parseFloat(branch),
            functions: parseFloat(funcs),
            lines: parseFloat(lines),
            uncoveredLines: uncovered.trim() || undefined
          });
        }
      }
    }
    
    return coverageData;
  };
  
  const parseCoverageSummary = (logs: string[]): TestExecutionState['coverage']['summary'] | undefined => {
    // Look for "Statements   : 37.17% ( 9466/25466 )"
    for (const line of logs) {
      if (line.includes('Statements') && line.includes('%')) {
        const stmtMatch = line.match(/Statements\s*:\s*([\d.]+)%\s*\(\s*(\d+)\/(\d+)\s*\)/);
        const branchLine = logs[logs.indexOf(line) + 1];
        const funcLine = logs[logs.indexOf(line) + 2];
        const linesLine = logs[logs.indexOf(line) + 3];
        
        if (stmtMatch && branchLine && funcLine && linesLine) {
          const branchMatch = branchLine.match(/Branches\s*:\s*([\d.]+)%\s*\(\s*(\d+)\/(\d+)\s*\)/);
          const funcMatch = funcLine.match(/Functions\s*:\s*([\d.]+)%\s*\(\s*(\d+)\/(\d+)\s*\)/);
          const linesMatch = linesLine.match(/Lines\s*:\s*([\d.]+)%\s*\(\s*(\d+)\/(\d+)\s*\)/);
          
          if (branchMatch && funcMatch && linesMatch) {
            return {
              statements: { value: parseInt(stmtMatch[2]), total: parseInt(stmtMatch[3]) },
              branches: { value: parseInt(branchMatch[2]), total: parseInt(branchMatch[3]) },
              functions: { value: parseInt(funcMatch[2]), total: parseInt(funcMatch[3]) },
              lines: { value: parseInt(linesMatch[2]), total: parseInt(linesMatch[3]) }
            };
          }
        }
      }
    }
    return undefined;
  };

  const updateSummaryFromLogs = (logs: string[]) => {
    const summaryData: Partial<TestExecutionState> = {};
    
    // Look for all summary lines
    for (const line of logs) {
      // Test Files summary
      const filesSummaryMatch = line.match(/Test Files\s+(?:(\d+)\s+failed\s*\|)?\s*(?:(\d+)\s+passed)?(?:\s*\|\s*(\d+)\s+skipped)?\s*\((\d+)\)/);
      if (filesSummaryMatch) {
        const [, failed, passed, skipped, total] = filesSummaryMatch;
        summaryData.fileSummary = {
          failed: parseInt(failed || '0'),
          passed: parseInt(passed || '0'),
          skipped: parseInt(skipped || '0'),
          total: parseInt(total)
        };
      }

      // Individual tests summary
      const testsMatch = line.match(/Tests\s+(?:(\d+)\s+failed\s*\|)?\s*(?:(\d+)\s+passed)?(?:\s*\|\s*(\d+)\s+skipped)?\s*\((\d+)\)/);
      if (testsMatch) {
        const [, failed, passed, skipped, total] = testsMatch;
        summaryData.testSummary = {
          failed: parseInt(failed || '0'),
          passed: parseInt(passed || '0'),
          skipped: parseInt(skipped || '0'),
          total: parseInt(total)
        };
      }
      
      // Error count
      const errorMatch = line.match(/Errors\s+(\d+)\s+errors?/);
      if (errorMatch) {
        summaryData.errorCount = parseInt(errorMatch[1]);
      }
      
      // Start time
      const startMatch = line.match(/Start at\s+(.+)/);
      if (startMatch) {
        summaryData.startTime = startMatch[1];
      }
      
      // Duration
      const durationMatch = line.match(/Duration\s+([\d.]+)s/);
      if (durationMatch) {
        summaryData.duration = parseFloat(durationMatch[1]);
      }
    }
    
    // Parse coverage data if test completed
    if (summaryData.fileSummary || summaryData.testSummary) {
      const coverageFiles = parseCoverageTable(logs);
      const coverageSummary = parseCoverageSummary(logs);
      
      if (coverageSummary && coverageFiles.length > 0) {
        summaryData.coverage = {
          summary: coverageSummary,
          files: coverageFiles
        };
      }
    }
    
    return summaryData;
  };

  const handleStreamMessage = (testType: TestType, message: TestStreamMessage) => {
    updateTestState(testType, (prev) => {
      // Keep only last 1000 logs to prevent memory issues
      const newLogs = [...prev.logs];
      if (newLogs.length > 1000) {
        newLogs.splice(0, newLogs.length - 1000);
      }
      let newResults = [...prev.results];

      switch (message.type) {
        case 'status':
          if (message.data?.status) {
            newLogs.push(`> Status: ${message.data.status}`);
          }
          break;
        case 'output':
          if (message.message !== undefined) {
            // Add all output lines to show in terminal
            newLogs.push(message.message);
            
            // Parse test results immediately as they come in
            const testResult = parseTestOutput(message.message);
            if (testResult) {
              console.log('[PARSED] Test result:', testResult);
              // Only add file-level results, not individual tests
              if (testResult.name.endsWith('.ts') || testResult.name.endsWith('.tsx') || 
                  testResult.name.endsWith('.js') || testResult.name.endsWith('.jsx')) {
                newResults.push(testResult);
              }
            }
            
            // Look for summary lines
            if (message.message.includes('Test Files') || 
                message.message.includes('Tests ') ||
                message.message.includes('passed') ||
                message.message.includes('failed')) {
              console.log('[SUMMARY CHECK]', message.message);
              const summaryData = updateSummaryFromLogs([...newLogs]);
              if (summaryData) {
                console.log('[SUMMARY FOUND]', summaryData);
                return {
                  ...prev,
                  logs: newLogs,
                  results: newResults,
                  ...summaryData,
                  isRunning: true // Still running until we get completed message
                };
              }
            }
            
          }
          break;
        case 'completed':
          newLogs.push('> Test execution completed.');
          const finalSummary = updateSummaryFromLogs(newLogs);
          return {
            ...prev,
            logs: newLogs,
            results: newResults,
            ...finalSummary,
            isRunning: false,
            duration: message.data?.duration || finalSummary.duration,
            exitCode: message.data?.exit_code
          };
        case 'error':
          newLogs.push(`> Error: ${message.message || 'Unknown error'}`);
          return {
            ...prev,
            logs: newLogs,
            results: newResults,
            isRunning: false,
            exitCode: 1
          };
        case 'cancelled':
          newLogs.push('> Test execution cancelled.');
          return {
            ...prev,
            logs: newLogs,
            results: newResults,
            isRunning: false,
            exitCode: -1
          };
      }

      return {
        ...prev,
        logs: newLogs,
        results: newResults,
        isRunning: true
      };
    });
  };

  const runTest = async (testType: TestType) => {
    try {
      // Reset test state
      updateTestState(testType, (prev) => ({
        ...prev,
        logs: [`> Starting ${testType === 'mcp' ? 'Python' : 'React UI'} tests...`],
        results: [],
        fileSummary: undefined,
        testSummary: undefined,
        errorCount: undefined,
        coverage: undefined,
        isRunning: true,
        duration: undefined,
        exitCode: undefined,
        startTime: new Date().toISOString()
      }));

      if (testType === 'mcp') {
        // Python tests: Use backend API with WebSocket streaming
        const execution = await testService.runMCPTests();
        
        // Update state with execution info
        updateTestState(testType, (prev) => ({
          ...prev,
          execution,
          logs: [...prev.logs, `> Execution ID: ${execution.execution_id}`, '> Connecting to real-time stream...']
        }));

        // Connect to WebSocket stream for real-time updates
        const cleanup = testService.connectToTestStream(
          execution.execution_id,
          (message) => handleStreamMessage(testType, message),
          (error) => {
            console.error('WebSocket error:', error);
            updateTestState(testType, (prev) => ({
              ...prev,
              logs: [...prev.logs, '> WebSocket connection error'],
              isRunning: false
            }));
            showToast('WebSocket connection error', 'error');
          },
          (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            // Only update state if it wasn't a normal closure
            if (event.code !== 1000) {
              updateTestState(testType, (prev) => ({
                ...prev,
                isRunning: false
              }));
            }
          }
        );

        // Store cleanup function
        wsCleanupRefs.current.set(execution.execution_id, cleanup);
        
      } else if (testType === 'ui') {
        // React tests: Run locally in frontend
        const execution_id = await testService.runUITestsWithStreaming(
          (message) => handleStreamMessage(testType, message),
          (error) => {
            console.error('UI test error:', error);
            updateTestState(testType, (prev) => ({
              ...prev,
              logs: [...prev.logs, `> Error: ${error.message}`],
              isRunning: false,
              exitCode: 1
            }));
            showToast('React test execution error', 'error');
          },
          () => {
            console.log('UI tests completed');
          }
        );

        // Update state with execution info
        updateTestState(testType, (prev) => ({
          ...prev,
          execution: {
            execution_id,
            test_type: 'ui',
            status: 'running',
            start_time: new Date().toISOString()
          },
          logs: [...prev.logs, `> Execution ID: ${execution_id}`, '> Running tests locally...']
        }));
      }

    } catch (error) {
      console.error(`Failed to run ${testType} tests:`, error);
      updateTestState(testType, (prev) => ({
        ...prev,
        logs: [...prev.logs, `> Error: ${error instanceof Error ? error.message : 'Unknown error'}`],
        isRunning: false,
        exitCode: 1
      }));
      showToast(`Failed to run ${testType} tests`, 'error');
    }
  };

  const cancelTest = async (testType: TestType) => {
    const currentState = testType === 'mcp' ? mcpTest : uiTest;
    
    if (currentState.execution?.execution_id) {
      try {
        await testService.cancelTestExecution(currentState.execution.execution_id);
        
        // Clean up WebSocket connection
        const cleanup = wsCleanupRefs.current.get(currentState.execution.execution_id);
        if (cleanup) {
          cleanup();
          wsCleanupRefs.current.delete(currentState.execution.execution_id);
        }
        
        updateTestState(testType, (prev) => ({
          ...prev,
          logs: [...prev.logs, '> Test execution cancelled by user'],
          isRunning: false,
          exitCode: -1
        }));

        showToast(`${testType.toUpperCase()} test execution cancelled`, 'success');
      } catch (error) {
        console.error(`Failed to cancel ${testType} tests:`, error);
        showToast(`Failed to cancel ${testType} tests`, 'error');
      }
    }
  };

  const getStatusIcon = (testState: TestExecutionState) => {
    if (testState.isRunning) {
      return <RefreshCw className="w-4 h-4 animate-spin text-orange-500" />;
    }
    if (testState.exitCode === 0) {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
    if (testState.exitCode === -1) {
      return <Square className="w-4 h-4 text-gray-500" />;
    }
    if (testState.exitCode === 1) {
      return <XCircle className="w-4 h-4 text-red-500" />;
    }
    return <Clock className="w-4 h-4 text-gray-400" />;
  };

  const getStatusText = (testState: TestExecutionState) => {
    if (testState.isRunning) return 'Running...';
    if (testState.exitCode === 0) return 'Passed';
    if (testState.exitCode === -1) return 'Cancelled';
    if (testState.exitCode === 1) return 'Failed';
    return 'Ready';
  };

  const formatLogLine = (log: string, index: number) => {
    let textColor = 'text-gray-300';
    
    // Test results
    if (log.includes('✓') || log.includes('passed')) textColor = 'text-green-400';
    if (log.includes('×') || log.includes('❯') || log.includes('failed')) textColor = 'text-red-400';
    if (log.includes('⚠') || log.includes('skipped')) textColor = 'text-yellow-400';
    
    // Errors and warnings
    if (log.includes('Error:') || log.includes('ERROR') || log.includes('FAIL')) textColor = 'text-red-400';
    if (log.includes('Warning:') || log.includes('WARN')) textColor = 'text-yellow-400';
    
    // Summary lines
    if (log.includes('Test Files') || log.includes('Tests ') || log.includes('Duration') || log.includes('Start at')) textColor = 'text-cyan-400';
    
    // Status messages
    if (log.startsWith('>')) textColor = 'text-blue-400';
    
    // Coverage table headers
    if (log.includes('% Stmts') || log.includes('Coverage summary')) textColor = 'text-gray-400 font-bold';

    return (
      <div key={index} className={`${textColor} leading-relaxed`}>
        {log}
      </div>
    );
  };

    const renderCoverageBar = (percent: number, label: string) => {
    const color = percent >= 80 ? 'bg-green-500' : percent >= 50 ? 'bg-yellow-500' : 'bg-red-500';
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-400 w-20">{label}:</span>
        <div className="flex-1 bg-gray-700 rounded-full h-2 overflow-hidden">
          <div 
            className={`${color} h-full transition-all duration-300`}
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="text-xs text-gray-300 w-12 text-right">{percent.toFixed(1)}%</span>
      </div>
    );
  };

  const renderPrettyResults = (testState: TestExecutionState, testType: TestType) => {
    const hasErrors = testState.errorCount && testState.errorCount > 0;
    const isErrorsExpanded = testType === 'mcp' ? mcpErrorsExpanded : uiErrorsExpanded;
    const setErrorsExpanded = testType === 'mcp' ? setMcpErrorsExpanded : setUiErrorsExpanded;
    
    // Use test summary for the main display
    const summary = testState.testSummary || testState.fileSummary;
    const total = summary?.total || 0;
    const passed = summary?.passed || 0;
    const failed = summary?.failed || 0;
    const skipped = summary?.skipped || 0;
    const passPercent = total > 0 ? Math.round((passed / total) * 100) : 0;
    const failPercent = total > 0 ? Math.round((failed / total) * 100) : 0;
    const skipPercent = total > 0 ? Math.round((skipped / total) * 100) : 0;
    
    // Calculate current progress during execution
    const currentFileCount = testState.results.length;
    const totalFiles = testState.fileSummary?.total || 74; // Use known total or fallback
    
    // Calculate available height for terminal
    const summaryHeight = (testState.fileSummary || testState.testSummary || testState.coverage) && !testState.isRunning ? 300 : 0;
    const progressHeight = testState.isRunning ? 80 : 0; // Height for progress bar
    const errorHeaderHeight = hasErrors ? 32 : 0; // 32px for error header
    const availableHeight = isErrorsExpanded ? 0 : (256 - summaryHeight - progressHeight - errorHeaderHeight - 16); // Terminal height

    return (
      <div className="h-full flex flex-col relative">
        {/* Test Summary - Show after completion */}
        {(testState.fileSummary || testState.testSummary) && !testState.isRunning && (
          <div className="mb-3 bg-gray-800 rounded-lg p-3">
            <div className="font-mono text-xs space-y-1">
              {/* Test Files Summary */}
              {testState.fileSummary && (
                <div className="text-gray-300">
                  <span className="text-gray-400">Test Files  </span>
                  {testState.fileSummary.failed > 0 && (
                    <span className="text-red-400">{testState.fileSummary.failed} failed | </span>
                  )}
                  <span className="text-green-400">{testState.fileSummary.passed} passed </span>
                  {testState.fileSummary.skipped > 0 && (
                    <span className="text-yellow-400">| {testState.fileSummary.skipped} skipped </span>
                  )}
                  <span className="text-gray-400">({testState.fileSummary.total})</span>
                </div>
              )}
              
              {/* Individual Tests Summary */}
              {testState.testSummary && (
                <div className="text-gray-300">
                  <span className="text-gray-400">     Tests  </span>
                  {testState.testSummary.failed > 0 && (
                    <span className="text-red-400">{testState.testSummary.failed} failed | </span>
                  )}
                  <span className="text-green-400">{testState.testSummary.passed} passed </span>
                  {testState.testSummary.skipped > 0 && (
                    <span className="text-yellow-400">| {testState.testSummary.skipped} skipped </span>
                  )}
                  <span className="text-gray-400">({testState.testSummary.total})</span>
                </div>
              )}
              
              {/* Error Count */}
              {testState.errorCount !== undefined && testState.errorCount > 0 && (
                <div className="text-gray-300">
                  <span className="text-gray-400">    Errors  </span>
                  <span className="text-orange-400">{testState.errorCount} errors</span>
                </div>
              )}
              
              {/* Time Info */}
              {testState.startTime && (
                <div className="text-gray-300">
                  <span className="text-gray-400">  Start at  </span>
                  <span>{testState.startTime}</span>
                </div>
              )}
              
              {/* Duration */}
              {testState.duration && (
                <div className="text-gray-300">
                  <span className="text-gray-400">  Duration  </span>
                  <span>{testState.duration.toFixed(2)}s</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Running Progress - Simple */}
        {testState.isRunning && (
          <div className="bg-gray-800 rounded-lg p-3 mb-3">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-orange-500" />
                <span className="text-sm font-medium text-gray-300">Running tests...</span>
              </div>
              <span className="text-xs text-gray-400">
                {currentFileCount} / {totalFiles} files
              </span>
            </div>
            
            {/* Progress bar */}
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div 
                className="bg-orange-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${(currentFileCount / totalFiles) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Terminal output - show all logs */}
        {!isErrorsExpanded && (
          <div 
            ref={testType === 'mcp' ? mcpTerminalRef : uiTerminalRef}
            className="flex-1 overflow-y-auto bg-gray-900 p-2 rounded font-mono text-xs" 
            style={{ maxHeight: `${availableHeight}px` }}
          >
            {testState.logs.map((log, index) => formatLogLine(log, index))}
          </div>
        )}

        {/* Collapsible errors section */}
        {hasErrors && (
          <div 
            className={`transition-all duration-300 ease-in-out ${
              isErrorsExpanded ? 'absolute inset-0 flex flex-col' : 'flex-shrink-0 mt-auto -mx-4 -mb-4'
            }`}
          >
            {/* Error header with toggle */}
            <button
              onClick={() => setErrorsExpanded(!isErrorsExpanded)}
              className="w-full flex items-center justify-between p-2 bg-red-100/80 dark:bg-red-900/20 border border-red-300 dark:border-red-800 hover:bg-red-200 dark:hover:bg-red-900/30 transition-all duration-300 ease-in-out flex-shrink-0"
            >
              <div className="flex items-center gap-2">
                <XCircle className="w-3 h-3 text-red-600 dark:text-red-400" />
                <h4 className="text-xs font-medium text-red-600 dark:text-red-400">
                  Errors ({testState.errorCount || 0})
                </h4>
              </div>
              <div className={`transform transition-transform duration-300 ease-in-out ${isErrorsExpanded ? 'rotate-180' : ''}`}>
                <ChevronUp className="w-4 h-4 text-red-600 dark:text-red-400" />
              </div>
            </button>
            
            {/* Collapsible error content */}
            <div 
              className={`bg-red-50 dark:bg-red-900/20 border-x border-b border-red-300 dark:border-red-800 overflow-hidden transition-all duration-300 ease-in-out ${
                isErrorsExpanded ? 'flex-1' : 'h-0'
              }`}
            >
              <div className="h-full overflow-y-auto p-2 space-y-2">
                {testState.logs
                  .filter(log => log.includes('Error:') || log.includes('ERROR') || log.includes('FAILED') || log.includes('AssertionError') || log.includes('Traceback'))
                  .map((log, index) => {
                    const isMainError = log.includes('ERROR:') || log.includes('FAILED');
                    const isAssertion = log.includes('AssertionError');
                    const isTraceback = log.includes('Traceback') || log.includes('File "');
                    
                    return (
                      <div key={index} className={`p-2 rounded ${
                        isMainError ? 'bg-red-200/80 dark:bg-red-800/30 border-l-4 border-red-500' :
                        isAssertion ? 'bg-red-100/80 dark:bg-red-700/20 border-l-2 border-red-400' :
                        isTraceback ? 'bg-gray-100 dark:bg-gray-800/50 border-l-2 border-gray-500' :
                        'bg-red-50 dark:bg-red-900/10'
                      }`}>
                        <div className="text-red-700 dark:text-red-300 text-xs font-mono whitespace-pre-wrap break-words">
                          {log}
                        </div>
                        {isMainError && (
                          <div className="mt-1 text-xs text-red-600 dark:text-red-400">
                            <span className="font-medium">Error Type:</span> {
                              log.includes('Health_check') ? 'Health Check Failure' :
                              log.includes('AssertionError') ? 'Test Assertion Failed' :
                              log.includes('NoneType') ? 'Null Reference Error' :
                              'General Error'
                            }
                          </div>
                        )}
                      </div>
                    );
                  })}
                
                {/* Error summary */}
                <div className="mt-4 p-2 bg-red-100/80 dark:bg-red-900/30 rounded border border-red-300 dark:border-red-700">
                  <h5 className="text-red-600 dark:text-red-400 font-medium text-xs mb-2">Error Summary:</h5>
                  <div className="text-xs text-red-700 dark:text-red-300 space-y-1">
                    <div>Total Errors: {testState.logs.filter(log => log.includes('ERROR:') || log.includes('FAILED')).length}</div>
                    <div>Assertion Failures: {testState.logs.filter(log => log.includes('AssertionError')).length}</div>
                    <div>Test Type: {testType === 'mcp' ? 'Python MCP Tools' : 'React UI Components'}</div>
                    <div>Status: Failed</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const TestSection = ({ 
    title, 
    testType, 
    testState, 
    onRun, 
    onCancel 
  }: { 
    title: string; 
    testType: TestType; 
    testState: TestExecutionState; 
    onRun: () => void; 
    onCancel: () => void; 
  }) => (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="text-md font-medium text-gray-700 dark:text-gray-300">
            {title}
          </h3>
          {getStatusIcon(testState)}
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {getStatusText(testState)}
          </span>
          {testState.duration && (
            <span className="text-xs text-gray-400">
              ({testState.duration.toFixed(1)}s)
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {/* Test Results button for React UI tests only */}
          {testType === 'ui' && hasResults && !testState.isRunning && (
            <Button
              variant="outline"
              accentColor="blue"
              size="sm"
              onClick={() => setShowTestResultsModal(true)}
            >
              <BarChart className="w-4 h-4 mr-2" />
              Test Results
            </Button>
          )}
          {testState.isRunning ? (
            <Button
              variant="outline"
              accentColor="pink"
              size="sm"
              onClick={onCancel}
            >
              <Square className="w-4 h-4 mr-2" />
              Cancel
            </Button>
          ) : (
            <Button
              variant="primary"
              accentColor="orange"
              size="sm"
              onClick={onRun}
              className="shadow-lg shadow-orange-500/20"
            >
              <Play className="w-4 h-4 mr-2" />
              Run Tests
            </Button>
          )}
        </div>
      </div>
      
      <div className="bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-md p-4 h-64 relative">
        {renderPrettyResults(testState, testType)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between cursor-pointer" onClick={() => setIsCollapsed(!isCollapsed)}>
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-orange-500 dark:text-orange-400 filter drop-shadow-[0_0_8px_rgba(251,146,60,0.8)]" />
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white">Archon Unit Tests</h2>
          <div className={`transform transition-transform duration-300 ${isCollapsed ? '' : 'rotate-180'}`}>
            <ChevronDown className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </div>
        </div>
        
        {/* Display mode toggle - only visible when expanded */}
        {!isCollapsed && (
          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <Button
              variant={displayMode === 'pretty' ? 'primary' : 'outline'}
              accentColor="blue"
              size="sm"
              onClick={() => setDisplayMode('pretty')}
            >
              <CheckCircle className="w-4 h-4 mr-1" />
              Summary
            </Button>
          </div>
        )}
      </div>

      {/* Collapsible content */}
      <div className={`space-y-4 transition-all duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
        <TestSection
          title="Python Tests"
          testType="mcp"
          testState={mcpTest}
          onRun={() => runTest('mcp')}
          onCancel={() => cancelTest('mcp')}
        />

        <TestSection
          title="React UI Tests"
          testType="ui"
          testState={uiTest}
          onRun={() => runTest('ui')}
          onCancel={() => cancelTest('ui')}
        />
      </div>

      {/* Test Results Modal */}
      <TestResultsModal 
        isOpen={showTestResultsModal} 
        onClose={() => setShowTestResultsModal(false)} 
      />
    </div>
  );
};
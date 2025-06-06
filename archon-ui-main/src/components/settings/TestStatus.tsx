import { useState, useEffect, useRef } from 'react';
import { Terminal, RefreshCw, Play, Square, Clock, CheckCircle, XCircle } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { testService, TestExecution, TestStreamMessage, TestType } from '../../services/testService';
import { useToast } from '../../contexts/ToastContext';

interface TestExecutionState {
  execution?: TestExecution;
  logs: string[];
  isRunning: boolean;
  duration?: number;
  exitCode?: number;
}

export const TestStatus = () => {
  const [mcpTest, setMcpTest] = useState<TestExecutionState>({
    logs: ['> Ready to run Python tests...'],
    isRunning: false
  });
  
  const [uiTest, setUiTest] = useState<TestExecutionState>({
    logs: ['> Ready to run React UI tests...'],
    isRunning: false
  });

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

  const handleStreamMessage = (testType: TestType, message: TestStreamMessage) => {
    updateTestState(testType, (prev) => {
      const newLogs = [...prev.logs];

      switch (message.type) {
        case 'status':
          if (message.data?.status) {
            newLogs.push(`> Status: ${message.data.status}`);
          }
          break;
        case 'output':
          if (message.message) {
            newLogs.push(message.message);
          }
          break;
        case 'completed':
          newLogs.push('> Test execution completed.');
          return {
            ...prev,
            logs: newLogs,
            isRunning: false,
            duration: message.data?.duration,
            exitCode: message.data?.exit_code
          };
        case 'error':
          newLogs.push(`> Error: ${message.message || 'Unknown error'}`);
          return {
            ...prev,
            logs: newLogs,
            isRunning: false,
            exitCode: 1
          };
        case 'cancelled':
          newLogs.push('> Test execution cancelled.');
          return {
            ...prev,
            logs: newLogs,
            isRunning: false,
            exitCode: -1
          };
      }

      return {
        ...prev,
        logs: newLogs
      };
    });
  };

  const runTest = async (testType: TestType) => {
    try {
      // Reset test state
      updateTestState(testType, (prev) => ({
        ...prev,
        logs: [`> Starting ${testType === 'mcp' ? 'Python' : 'React UI'} tests...`],
        isRunning: true,
        duration: undefined,
        exitCode: undefined
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
    if (log.includes('PASS') || log.includes('✓') || log.includes('passed')) textColor = 'text-green-400';
    if (log.includes('FAIL') || log.includes('✕') || log.includes('failed')) textColor = 'text-red-400';
    if (log.includes('Error:') || log.includes('ERROR')) textColor = 'text-red-400';
    if (log.includes('Warning:') || log.includes('WARN')) textColor = 'text-yellow-400';
    if (log.includes('Status:') || log.includes('Duration:') || log.includes('Execution ID:')) textColor = 'text-cyan-400';
    if (log.startsWith('>')) textColor = 'text-blue-400';

    return (
      <div key={index} className={`${textColor} py-0.5 whitespace-pre-wrap font-mono`}>
        {log}
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
      <div className="bg-gray-900 border border-gray-800 rounded-md p-4 h-64 overflow-y-auto font-mono text-xs">
        {testState.logs.map((log, index) => formatLogLine(log, index))}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Terminal className="w-5 h-5 text-orange-400" />
        <h2 className="text-xl font-semibold text-white">Test Status</h2>
      </div>

      <div className="space-y-4">
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
    </div>
  );
};
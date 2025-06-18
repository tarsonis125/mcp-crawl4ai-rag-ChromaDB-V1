import { credentialsService } from './credentialsService';

interface HealthCheckCallback {
  onDisconnected: () => void;
  onReconnected: () => void;
}

class ServerHealthService {
  private healthCheckInterval: number | null = null;
  private wsHealthInterval: number | null = null;
  private isConnected: boolean = true;
  private missedPings: number = 0;
  private callbacks: HealthCheckCallback | null = null;
  private ws: WebSocket | null = null;
  private reconnectTimeout: number | null = null;

  // Settings
  private disconnectScreenEnabled: boolean = true;
  private disconnectScreenDelay: number = 10000; // 10 seconds

  async loadSettings() {
    try {
      // Load disconnect screen settings from API
      const enabledRes = await credentialsService.getCredential('DISCONNECT_SCREEN_ENABLED').catch(() => ({ value: 'true' }));
      this.disconnectScreenEnabled = enabledRes.value === 'true';
    } catch (error) {
      console.error('Failed to load disconnect screen settings:', error);
    }
  }

  async updateSettings(enabled: boolean) {
    this.disconnectScreenEnabled = enabled;

    // Save to backend
    try {
      await credentialsService.createCredential({
        key: 'DISCONNECT_SCREEN_ENABLED',
        value: enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable disconnect screen when server is disconnected'
      });
    } catch (error) {
      console.error('Failed to save disconnect screen settings:', error);
    }
  }

  getSettings() {
    return {
      enabled: this.disconnectScreenEnabled,
      delay: this.disconnectScreenDelay
    };
  }

  startMonitoring(callbacks: HealthCheckCallback) {
    this.callbacks = callbacks;
    this.missedPings = 0;
    this.isConnected = true;

    // Load settings first
    this.loadSettings();

    // Start WebSocket health monitoring
    this.connectWebSocket();

    // Fallback HTTP health check every 2 seconds
    this.healthCheckInterval = window.setInterval(() => {
      this.checkHealth();
    }, 2000);
  }

  private connectWebSocket() {
    try {
      // Use the same WebSocket URL pattern as other services
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/health`;
      
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('Health WebSocket connected');
        this.missedPings = 0;
        this.handleConnectionRestored();

        // Send ping every 2 seconds
        this.wsHealthInterval = window.setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 2000);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') {
            this.missedPings = 0;
            this.handleConnectionRestored();
          }
        } catch (error) {
          console.error('Failed to parse health message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('Health WebSocket disconnected');
        if (this.wsHealthInterval) {
          window.clearInterval(this.wsHealthInterval);
          this.wsHealthInterval = null;
        }

        // Try to reconnect after 5 seconds
        this.reconnectTimeout = window.setTimeout(() => {
          this.connectWebSocket();
        }, 5000);
      };

      this.ws.onerror = (error) => {
        console.error('Health WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect health WebSocket:', error);
    }
  }

  private async checkHealth() {
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.ready) {
          this.missedPings = 0;
          this.handleConnectionRestored();
        } else {
          // Server is starting up
          this.handleMissedPing();
        }
      } else {
        this.handleMissedPing();
      }
    } catch (error) {
      this.handleMissedPing();
    }
  }

  private handleMissedPing() {
    this.missedPings++;
    
    // After 5 missed pings (10 seconds), trigger screensaver
    if (this.missedPings >= 5 && this.isConnected) {
      this.isConnected = false;
      if (this.disconnectScreenEnabled && this.callbacks) {
        this.callbacks.onDisconnected();
      }
    }
  }

  private handleConnectionRestored() {
    if (!this.isConnected) {
      this.isConnected = true;
      if (this.callbacks) {
        this.callbacks.onReconnected();
      }
    }
  }

  stopMonitoring() {
    if (this.healthCheckInterval) {
      window.clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }

    if (this.wsHealthInterval) {
      window.clearInterval(this.wsHealthInterval);
      this.wsHealthInterval = null;
    }

    if (this.reconnectTimeout) {
      window.clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.callbacks = null;
  }

  isServerConnected() {
    return this.isConnected;
  }
}

export const serverHealthService = new ServerHealthService();
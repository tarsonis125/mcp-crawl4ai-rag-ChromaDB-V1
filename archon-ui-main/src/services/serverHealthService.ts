import { credentialsService } from './credentialsService';

interface HealthCheckCallback {
  onDisconnected: () => void;
  onReconnected: () => void;
}

class ServerHealthService {
  private healthCheckInterval: number | null = null;
  private isConnected: boolean = true;
  private missedChecks: number = 0;
  private callbacks: HealthCheckCallback | null = null;

  // Settings
  private disconnectScreenEnabled: boolean = true;
  private disconnectScreenDelay: number = 10000; // 10 seconds
  private maxMissedChecks: number = 3; // Show disconnect after 3 missed checks
  private checkInterval: number = 3000; // Check every 3 seconds

  async loadSettings() {
    try {
      // Load disconnect screen settings from API
      const enabledRes = await credentialsService.getCredential('DISCONNECT_SCREEN_ENABLED').catch(() => ({ value: 'true' }));
      this.disconnectScreenEnabled = enabledRes.value === 'true';
    } catch (error) {
      // Failed to load disconnect screen settings
    }
  }

  async checkHealth(): Promise<boolean> {
    try {
      // Use the proxied /api/health endpoint which works in both dev and Docker
      const response = await fetch('/api/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      
      if (response.ok) {
        const data = await response.json();
        // Accept healthy, online, or initializing (server is starting up)
        return data.status === 'healthy' || data.status === 'online' || data.status === 'initializing';
      }
      return false;
    } catch (error) {
      // Health check failed
      return false;
    }
  }

  startMonitoring(callbacks: HealthCheckCallback) {
    this.callbacks = callbacks;
    this.missedChecks = 0;
    this.isConnected = true;

    // Load settings first
    this.loadSettings();

    // Start HTTP health polling
    this.healthCheckInterval = window.setInterval(async () => {
      const isHealthy = await this.checkHealth();
      
      if (isHealthy) {
        // Server is healthy
        if (this.missedChecks > 0) {
          // Was disconnected, now reconnected
          this.missedChecks = 0;
          this.handleConnectionRestored();
        }
      } else {
        // Server is not responding
        this.missedChecks++;
        // Health check failed
        
        // After maxMissedChecks failures, trigger disconnect screen
        if (this.missedChecks >= this.maxMissedChecks && this.isConnected) {
          this.isConnected = false;
          if (this.disconnectScreenEnabled && this.callbacks) {
            // Triggering disconnect screen after multiple health check failures
            this.callbacks.onDisconnected();
          }
        }
      }
    }, this.checkInterval);

    // Do an immediate check
    this.checkHealth().then(isHealthy => {
      if (!isHealthy) {
        this.missedChecks = 1;
      }
    });
  }

  private handleConnectionRestored() {
    if (!this.isConnected) {
      this.isConnected = true;
      // Connection to server restored
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
    this.callbacks = null;
  }

  isServerConnected(): boolean {
    return this.isConnected;
  }

  getSettings() {
    return {
      enabled: this.disconnectScreenEnabled,
      delay: this.disconnectScreenDelay
    };
  }

  async updateSettings(settings: { enabled?: boolean; delay?: number }) {
    if (settings.enabled !== undefined) {
      this.disconnectScreenEnabled = settings.enabled;
      await credentialsService.createCredential({
        key: 'DISCONNECT_SCREEN_ENABLED',
        value: settings.enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable disconnect screen when server is disconnected'
      });
    }
    
    if (settings.delay !== undefined) {
      this.disconnectScreenDelay = settings.delay;
      // You could save this to credentials as well if needed
    }
  }
}

export const serverHealthService = new ServerHealthService();
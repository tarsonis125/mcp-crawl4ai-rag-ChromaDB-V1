export interface Credential {
  id?: string;
  key: string;
  value?: string;
  encrypted_value?: string;
  is_encrypted: boolean;
  category: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RagSettings {
  USE_CONTEXTUAL_EMBEDDINGS: boolean;
  USE_HYBRID_SEARCH: boolean;
  USE_AGENTIC_RAG: boolean;
  USE_RERANKING: boolean;
  MODEL_CHOICE: string;
}

class CredentialsService {
  private baseUrl = (import.meta as any).env?.VITE_API_URL || this.getApiBaseUrl();

  private getApiBaseUrl() {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = '8080'; // Backend API port
    return `${protocol}//${host}:${port}`;
  }

  async getAllCredentials(): Promise<Credential[]> {
    const response = await fetch(`${this.baseUrl}/api/credentials`);
    if (!response.ok) {
      throw new Error('Failed to fetch credentials');
    }
    return response.json();
  }

  async getCredentialsByCategory(category: string): Promise<Credential[]> {
    const response = await fetch(`${this.baseUrl}/api/credentials?category=${category}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch credentials for category: ${category}`);
    }
    return response.json();
  }

  async getRagSettings(): Promise<RagSettings> {
    const ragCredentials = await this.getCredentialsByCategory('rag_strategy');
    const llmCredentials = await this.getCredentialsByCategory('llm_config');
    
    const settings: RagSettings = {
      USE_CONTEXTUAL_EMBEDDINGS: false,
      USE_HYBRID_SEARCH: false,
      USE_AGENTIC_RAG: false,
      USE_RERANKING: false,
      MODEL_CHOICE: 'gpt-4o-mini'
    };

    // Map credentials to settings
    [...ragCredentials, ...llmCredentials].forEach(cred => {
      if (cred.key in settings) {
        if (cred.key === 'MODEL_CHOICE') {
          settings[cred.key] = cred.value || 'gpt-4o-mini';
        } else {
          (settings as any)[cred.key] = cred.value === 'true';
        }
      }
    });

    return settings;
  }

  async updateCredential(credential: Credential): Promise<Credential> {
    const response = await fetch(`${this.baseUrl}/api/credentials/${credential.key}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credential),
    });
    
    if (!response.ok) {
      throw new Error('Failed to update credential');
    }
    
    return response.json();
  }

  async createCredential(credential: Credential): Promise<Credential> {
    const response = await fetch(`${this.baseUrl}/api/credentials`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credential),
    });
    
    if (!response.ok) {
      throw new Error('Failed to create credential');
    }
    
    return response.json();
  }

  async deleteCredential(key: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/credentials/${key}`, {
      method: 'DELETE',
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete credential');
    }
  }

  async updateRagSettings(settings: RagSettings): Promise<void> {
    const promises = [];
    
    // Update RAG strategy settings
    for (const [key, value] of Object.entries(settings)) {
      if (key !== 'MODEL_CHOICE') {
        promises.push(
          this.updateCredential({
            key,
            value: value.toString(),
            is_encrypted: false,
            category: 'rag_strategy',
          })
        );
      }
    }
    
    // Update model choice
    promises.push(
      this.updateCredential({
        key: 'MODEL_CHOICE',
        value: settings.MODEL_CHOICE,
        is_encrypted: false,
        category: 'llm_config',
      })
    );
    
    await Promise.all(promises);
  }
}

export const credentialsService = new CredentialsService(); 
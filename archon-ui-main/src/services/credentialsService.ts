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
  CONTEXTUAL_EMBEDDINGS_MAX_WORKERS: number;
  USE_HYBRID_SEARCH: boolean;
  USE_AGENTIC_RAG: boolean;
  USE_RERANKING: boolean;
  MODEL_CHOICE: string;
  LLM_PROVIDER?: string;
  LLM_BASE_URL?: string;
  EMBEDDING_MODEL?: string;
}

export interface CodeExtractionSettings {
  MIN_CODE_BLOCK_LENGTH: number;
  MAX_CODE_BLOCK_LENGTH: number;
  ENABLE_COMPLETE_BLOCK_DETECTION: boolean;
  ENABLE_LANGUAGE_SPECIFIC_PATTERNS: boolean;
  ENABLE_PROSE_FILTERING: boolean;
  MAX_PROSE_RATIO: number;
  MIN_CODE_INDICATORS: number;
  ENABLE_DIAGRAM_FILTERING: boolean;
  ENABLE_CONTEXTUAL_LENGTH: boolean;
  CODE_EXTRACTION_MAX_WORKERS: number;
  CONTEXT_WINDOW_SIZE: number;
  ENABLE_CODE_SUMMARIES: boolean;
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
    const response = await fetch(`${this.baseUrl}/api/credentials/categories/${category}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch credentials for category: ${category}`);
    }
    const result = await response.json();
    
    // The API returns {credentials: {...}} where credentials is a dict
    // Convert to array format expected by frontend
    if (result.credentials && typeof result.credentials === 'object') {
      return Object.entries(result.credentials).map(([key, value]: [string, any]) => {
        if (value && typeof value === 'object' && value.is_encrypted) {
          return {
            key,
            value: undefined,
            encrypted_value: value.encrypted_value,
            is_encrypted: true,
            category,
            description: value.description
          };
        } else {
          return {
            key,
            value: value,
            encrypted_value: undefined,
            is_encrypted: false,
            category,
            description: ''
          };
        }
      });
    }
    
    return [];
  }

  async getCredential(key: string): Promise<{ key: string; value?: string; is_encrypted?: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/credentials/${key}`);
    if (!response.ok) {
      if (response.status === 404) {
        // Return empty object if credential not found
        return { key, value: undefined };
      }
      throw new Error(`Failed to fetch credential: ${key}`);
    }
    return response.json();
  }

  async getRagSettings(): Promise<RagSettings> {
    const ragCredentials = await this.getCredentialsByCategory('rag_strategy');
    const apiKeysCredentials = await this.getCredentialsByCategory('api_keys');
    
    const settings: RagSettings = {
      USE_CONTEXTUAL_EMBEDDINGS: false,
      CONTEXTUAL_EMBEDDINGS_MAX_WORKERS: 3,
      USE_HYBRID_SEARCH: false,
      USE_AGENTIC_RAG: false,
      USE_RERANKING: false,
      MODEL_CHOICE: 'gpt-4.1-nano',
      LLM_PROVIDER: 'openai',
      LLM_BASE_URL: '',
      EMBEDDING_MODEL: ''
    };

    // Map credentials to settings
    [...ragCredentials, ...apiKeysCredentials].forEach(cred => {
      if (cred.key in settings) {
        if (cred.key === 'MODEL_CHOICE' || cred.key === 'LLM_PROVIDER' || cred.key === 'LLM_BASE_URL' || cred.key === 'EMBEDDING_MODEL') {
          (settings as any)[cred.key] = cred.value || '';
        } else if (cred.key === 'CONTEXTUAL_EMBEDDINGS_MAX_WORKERS') {
          settings[cred.key] = parseInt(cred.value || '3', 10);
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
        category: 'rag_strategy',
      })
    );
    
    await Promise.all(promises);
  }

  async getCodeExtractionSettings(): Promise<CodeExtractionSettings> {
    const codeExtractionCredentials = await this.getCredentialsByCategory('code_extraction');
    
    const settings: CodeExtractionSettings = {
      MIN_CODE_BLOCK_LENGTH: 250,
      MAX_CODE_BLOCK_LENGTH: 5000,
      ENABLE_COMPLETE_BLOCK_DETECTION: true,
      ENABLE_LANGUAGE_SPECIFIC_PATTERNS: true,
      ENABLE_PROSE_FILTERING: true,
      MAX_PROSE_RATIO: 0.15,
      MIN_CODE_INDICATORS: 3,
      ENABLE_DIAGRAM_FILTERING: true,
      ENABLE_CONTEXTUAL_LENGTH: true,
      CODE_EXTRACTION_MAX_WORKERS: 3,
      CONTEXT_WINDOW_SIZE: 1000,
      ENABLE_CODE_SUMMARIES: true
    };

    // Map credentials to settings
    codeExtractionCredentials.forEach(cred => {
      if (cred.key in settings) {
        const key = cred.key as keyof CodeExtractionSettings;
        if (typeof settings[key] === 'number') {
          if (key === 'MAX_PROSE_RATIO') {
            settings[key] = parseFloat(cred.value || '0.15');
          } else {
            settings[key] = parseInt(cred.value || settings[key].toString(), 10);
          }
        } else if (typeof settings[key] === 'boolean') {
          settings[key] = cred.value === 'true';
        }
      }
    });

    return settings;
  }

  async updateCodeExtractionSettings(settings: CodeExtractionSettings): Promise<void> {
    const promises = [];
    
    // Update all code extraction settings
    for (const [key, value] of Object.entries(settings)) {
      promises.push(
        this.updateCredential({
          key,
          value: value.toString(),
          is_encrypted: false,
          category: 'code_extraction',
        })
      );
    }
    
    await Promise.all(promises);
  }
}

export const credentialsService = new CredentialsService(); 
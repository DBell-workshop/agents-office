export interface AgentSpawnConfig {
  agentId: string;
  name: string;
  slug: string;
  spriteKey: string;
  homePosition: { x: number; y: number };
}

export type AgentState = 'idle' | 'think' | 'speak' | 'work' | 'walk' | 'complete' | 'error';

export interface AgentData {
  agent_id: string;
  name: string;
  slug: string;
  description: string;
  agent_type: string;
  status: string;
  model_config: Record<string, any>;
}

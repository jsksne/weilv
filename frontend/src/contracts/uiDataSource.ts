import type { AssistantContract } from './assistant'
import type { ShellContract } from './shell'

export interface UiDataSource {
  getShell(): Promise<ShellContract>
  getAssistant(): Promise<AssistantContract>
}

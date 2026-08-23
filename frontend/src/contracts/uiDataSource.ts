import type { ShellContract } from './shell'

export interface UiDataSource {
  getShell(): Promise<ShellContract>
}

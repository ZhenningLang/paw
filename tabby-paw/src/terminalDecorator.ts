import { Injectable, Inject } from '@angular/core'
import { HotkeysService, ConfigService } from 'tabby-core'
import { TerminalDecorator, BaseTerminalTabComponent } from 'tabby-terminal'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

function expandHome (p: string): string {
    return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p
}

function formatTimestamp (): string {
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

@Injectable()
export class PawTerminalDecorator extends TerminalDecorator {
    constructor (
        private hotkeys: HotkeysService,
        private config: ConfigService,
    ) {
        super()
    }

    attach (tab: BaseTerminalTabComponent<any>): void {
        // Cmd+Z → send 0x1f (undo)
        this.subscribeUntilDetached(tab, this.hotkeys.hotkey$.subscribe(hotkey => {
            if (hotkey === 'paw:terminal-undo') {
                tab.sendInput(Buffer.from([0x1f]).toString())
            }
        }))

        // Intercept paste → check for clipboard image
        this.subscribeUntilDetached(tab, this.hotkeys.hotkey$.subscribe(async hotkey => {
            if (hotkey === 'paste') {
                await this.handlePaste(tab)
            }
        }))
    }

    private async handlePaste (tab: BaseTerminalTabComponent<any>): Promise<void> {
        try {
            const remote = require('@electron/remote')
            const { clipboard } = remote
            const image = clipboard.readImage()
            if (image.isEmpty()) {
                return
            }

            const imageData = image.toPNG()
            const cfg = this.config.store.paw?.pasteImage ?? {}
            const saveDir = expandHome(cfg.saveDirectory || '~/.config/paw/images')

            if (!fs.existsSync(saveDir)) {
                fs.mkdirSync(saveDir, { recursive: true })
            }

            const filename = `clipboard_${formatTimestamp()}.png`
            const filepath = path.join(saveDir, filename)
            fs.writeFileSync(filepath, imageData)

            const fmt = cfg.outputFormat || '{path}'
            const output = fmt
                .replace('{path}', filepath)
                .replace('{filename}', filename)
                .replace('{dir}', saveDir)

            tab.sendInput(output)
        } catch (e) {
            // @electron/remote not available or other error — silently ignore
        }
    }
}

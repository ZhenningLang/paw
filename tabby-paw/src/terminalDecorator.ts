import { Injectable } from '@angular/core'
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

function readClipboardImage (): Buffer | null {
    try {
        const remote = require('@electron/remote')
        const image = remote.clipboard.readImage()
        if (!image.isEmpty()) {
            return image.toPNG()
        }
    } catch {
        // @electron/remote not available
    }
    try {
        const { clipboard } = require('electron')
        const image = clipboard.readImage()
        if (!image.isEmpty()) {
            return image.toPNG()
        }
    } catch {
        // fallback not available either
    }
    return null
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
        this.subscribeUntilDetached(tab, this.hotkeys.hotkey$.subscribe(hotkey => {
            if (hotkey === 'paw:terminal-undo') {
                tab.sendInput(Buffer.from([0x1f]).toString())
            }
        }))

        const origPaste = tab.paste.bind(tab)
        tab.paste = async () => {
            const imageData = readClipboardImage()
            if (imageData) {
                const filePath = this.saveImage(imageData)
                if (filePath) {
                    tab.sendInput(filePath)
                    return
                }
            }
            await origPaste()
        }
    }

    private saveImage (imageData: Buffer): string | null {
        try {
            const cfg = this.config.store.paw?.pasteImage ?? {}
            const saveDir = expandHome(cfg.saveDirectory || '~/.config/paw/images')

            if (!fs.existsSync(saveDir)) {
                fs.mkdirSync(saveDir, { recursive: true })
            }

            const filename = `clipboard_${formatTimestamp()}.png`
            const filepath = path.join(saveDir, filename)
            fs.writeFileSync(filepath, imageData)

            const fmt = cfg.outputFormat || '{path}'
            return fmt
                .replace('{path}', filepath)
                .replace('{filename}', filename)
                .replace('{dir}', saveDir)
        } catch {
            return null
        }
    }
}

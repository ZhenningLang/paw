import { Injectable } from '@angular/core'
import { HotkeyDescription, HotkeyProvider } from 'tabby-core'

@Injectable()
export class PawHotkeyProvider extends HotkeyProvider {
    async provide (): Promise<HotkeyDescription[]> {
        return [
            {
                id: 'paw:terminal-undo',
                name: 'Terminal Undo (send Ctrl+_)',
            },
        ]
    }
}

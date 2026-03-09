import { Injectable } from '@angular/core'
import { ConfigProvider } from 'tabby-core'

@Injectable()
export class PawConfigProvider extends ConfigProvider {
    defaults = {
        paw: {
            pasteImage: {
                saveDirectory: '~/.config/paw/images',
                filenameFormat: 'clipboard_%timestamp%.png',
                outputFormat: '{path}',
            },
        },
        hotkeys: {
            'paw:terminal-undo': ['⌘-Z'],
        },
    }
}

import { NgModule } from '@angular/core'
import { CommonModule } from '@angular/common'
import TabbyCoreModule, { ConfigProvider, HotkeyProvider } from 'tabby-core'
import { TerminalDecorator } from 'tabby-terminal'

import { PawConfigProvider } from './configProvider'
import { PawHotkeyProvider } from './hotkeyProvider'
import { PawTerminalDecorator } from './terminalDecorator'

@NgModule({
    imports: [CommonModule, TabbyCoreModule],
    providers: [
        { provide: ConfigProvider, useClass: PawConfigProvider, multi: true },
        { provide: HotkeyProvider, useClass: PawHotkeyProvider, multi: true },
        { provide: TerminalDecorator, useClass: PawTerminalDecorator, multi: true },
    ],
})
export default class PawModule {}

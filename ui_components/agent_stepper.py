from __future__ import annotations

from nicegui import ui


class ProgressItem(ui.item):
    """Timeline-style list item: dot + vertical line + free-form content."""

    def __init__(self, *, final: bool = False):
        super().__init__()
        with self:
            with ui.row().classes('w-full items-start no-wrap gap-2 overflow-clip mb-2'):
                # LEFT RAIL / ICON COLUMN
                with ui.column().classes('w-6 shrink-0 items-center self-stretch gap-0'):
                    if final:
                        # Replace dot + line with icon for final item
                        ui.icon('sym_o_checklist_rtl').classes('text-xl text-gray-500 mt-[2px]')
                    else:
                        with ui.row().classes('h-5 items-center justify-center'):
                            ui.element('div').classes('h-[6px] w-[6px] rounded-full bg-gray-400')
                        ui.element('div').classes('w-[1px] rounded-full grow bg-gray-300')

                # RIGHT CONTENT (free-form)
                self.container = ui.column().classes('grow min-w-0 gap-2')


class AgentStepper(ui.list):
    """Static agent stepper placeholder used while real agent wiring is in progress."""

    def __init__(self) -> None:
        super().__init__()
        self.props('dense').classes('w-full max-w-xl')
        with self:
            expansion = ui.expansion(text='Hello').props('dense').classes('w-full')
            with expansion.add_slot('header'):
                self._build_header()
            with expansion:
                self._build_body()

    @staticmethod
    def _build_header() -> None:
        with ui.item_section().classes('w-full'):
            with ui.row().classes('items-center gap-2'):
                with ui.column().classes('w-6 shrink-0 items-center justify-center'):
                    ui.icon('sym_o_token').classes('text-xl')
                ui.label('Hello! I am thinking!').classes('shimmer')

    def _build_body(self) -> None:
        with ui.list().props('dense').classes('w-full'):
            self._add_basic_steps()
            self._add_follow_up()
            self._add_search_card()
            self._add_simple_step()
            self._add_final_step()

    @staticmethod
    def _add_basic_steps() -> None:
        with ProgressItem() as item:
            with item.container:
                ui.label('Debugging invisible text')
                ui.label(
                    'Add a solid base layer under the gradient so the text remains visible '
                    'even when most of the gradient is transparent.'
                )

    @staticmethod
    def _add_follow_up() -> None:
        with ProgressItem() as item:
            with item.container:
                ui.label('Follow-up observation')
                ui.label(
                    'Confirmed the base background layer prevents the text from vanishing '
                    'across themes and backgrounds.'
                )

    @staticmethod
    def _add_search_card() -> None:
        with ProgressItem() as item:
            with item.container:
                with ui.row().classes('items-center gap-2'):
                    ui.icon('sym_o_search').classes('text-lg text-gray-600')
                    ui.label('Searching the web').classes('font-medium')

                with ui.card().props('flat bordered').classes('w-full bg-gray-50'):
                    with ui.column().classes('w-full gap-2'):
                        ui.label(
                            'Collected the latest reports on funding trends and competitor launches.'
                        ).classes('text-sm text-gray-600')

                        with ui.row().classes(
                            'w-full items-center no-wrap gap-2 bg-white border border-gray-200 rounded-lg px-3 py-2'
                        ):
                            ui.icon('sym_o_search')
                            ui.label(
                                'Latest startup funding trends 2025 fintech SaaS competitor analysis site'
                            ).classes('text-sm text-gray-700 grow min-w-0 truncate')

    @staticmethod
    def _add_simple_step() -> None:
        with ProgressItem() as item:
            with item.container:
                ui.label('Simple step')

    @staticmethod
    def _add_final_step() -> None:
        with ProgressItem(final=True) as item:
            with item.container:
                ui.label('Another placeholder step')

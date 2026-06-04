# src/services/selected_programs_service.py
from __future__ import annotations
from src.services.file_loading_service import ProgramSummary, LoadedSchedulerInput

# Static mapping for standard academic programs when raw data files aren't loaded yet
BASELINE_PROGRAM_NAMES: dict[str, str] = {
    "83101": "Computer Engineering",
    "83102": "Electrical Engineering",
    "83103": "Electrical Engineering - Neuro Engineering Track",
    "83104": "Industrial Engineering and Information Systems",
    "83105": "Computer Engineering - Computer Hardware Track",
    "83107": "Data Engineering",
    "83108": "Software Engineering",
    "83109": "Materials Engineering",
    "83115": "Electrical Engineering - Biomedical Engineering Track",
    "83182": "Electrical Engineering - Quantum Engineering Track",
}


class SelectedProgramsViewModel:
    """
    Manages the business logic and state for selected study programs.
    Keeps the internal data structures completely decoupled from PyQt.
    """

    def __init__(self) -> None:
        self._all_available_programs: dict[str, ProgramSummary] = {}
        self._selected_ids: list[str] = []

    def update_available_programs(self, loaded_data: LoadedSchedulerInput | None) -> None:
        """
        Updates the internal registry of available programs discovered from the loaded file.
        Clears the registry if no data is provided.
        """
        if not loaded_data or not loaded_data.programs:
            self._all_available_programs = {}
            return

        # Explicitly map string representations of IDs to their summary models
        self._all_available_programs = {
            str(p.program_id): p for p in loaded_data.programs
        }

    def set_selected_program_ids(self, program_ids: list[str]) -> None:
        """
        Updates the list of selected program identifiers chosen by the user.
        Preserves the original selection order.
        """
        # Create a shallow copy to prevent side-effects from external UI mutations
        self._selected_ids = list(program_ids)

    def get_selected_program_details(self) -> list[dict[str, str]]:
        """
        Returns a primitive, read-only data structure tailored for UI consumption.
        Each dictionary element contains the program ID and its formatted display name.
        """
        details = []
        for pid in self._selected_ids:
            # If the program exists in the dynamically loaded dataset, extract its dynamic display name
            if pid in self._all_available_programs:
                prog = self._all_available_programs[pid]
                details.append({
                    "program_id": pid,
                    "display_name": prog.display_name
                })
            else:
                # Fallback mechanism translating known baseline codes into official English titles
                resolved_name = BASELINE_PROGRAM_NAMES.get(pid, f"Program {pid}")
                details.append({
                    "program_id": pid,
                    "display_name": resolved_name
                })
        return details
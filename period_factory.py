from datetime import datetime, date
from base_factory import BaseFactory
from scheduling import ExamPeriod, DateExclusion
from enums import Semester, Term

SEMESTER_MAP = {
    "FALL": Semester.FALL,
    "SPRI": Semester.SPRING,
    "SUMM": Semester.SUMMER,
}

TERM_MAP = {
    "Aleph": Term.ALEPH,
    "Bet":   Term.BET,
    "Gimel": Term.GIMEL,
}


class PeriodFactory(BaseFactory[ExamPeriod]):
    """Builds ExamPeriod objects from periods_node entries."""

    def _build_one(self, period_dict: dict) -> ExamPeriod:
        period = ExamPeriod(
            semester   = SEMESTER_MAP[period_dict["semester"]],
            term       = TERM_MAP[period_dict["moed"]],
            start_date = self._parse_date(period_dict["start_date"]),
            end_date   = self._parse_date(period_dict["end_date"]),
        )
        for exclusion in period_dict["exclusions"]:
            period.add_exclusion(self._build_exclusion(exclusion))
        return period

    def _build_exclusion(self, date_dict: dict) -> DateExclusion:
        start = self._parse_date(date_dict["start_date"])
        end   = self._parse_date(date_dict["end_date"]) if date_dict.get("end_date") else None
        return DateExclusion(start_date=start, end_date=end)

    @staticmethod
    def _parse_date(date_str: str) -> date:
        return datetime.strptime(date_str, "%d-%m-%Y").date()


def build_periods_from_json(json_str: str) -> list[ExamPeriod]:
    return PeriodFactory().build_all(json_str, "periods_node")
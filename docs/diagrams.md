# Diagrams

These diagrams match the current project structure and file names.

Exported image and PDF versions are available in:

```text
docs/diagram_exports/
```

## System Workflow

```mermaid
flowchart TD
    User["User"] --> Main["main.py"]
    Main --> Args["Parse CLI arguments"]
    Args --> Workflow["src/workflow.py"]

    Workflow --> Parser["FileParser"]
    Parser --> CourseData["Course records"]
    Parser --> PeriodData["Exam period records"]
    Parser --> ProgramData["Selected programs"]

    CourseData --> Factories["CourseFactory and PeriodFactory"]
    PeriodData --> Factories
    ProgramData --> Filter["filter_courses_for_period"]
    Factories --> Filter

    Filter --> PeriodScheduler["period_scheduler.Scheduler"]
    PeriodScheduler --> Rule["AcademicConflictRule"]
    Rule --> PeriodSchedules["Valid period schedules"]

    PeriodSchedules --> ModeDecision{"Selected mode"}
    ModeDecision --> PeriodMode["period output"]
    ModeDecision --> CountMode["complete-count"]
    ModeDecision --> WriteMode["complete-write"]
    ModeDecision --> AutoMode["auto write within time limit"]

    CountMode --> CompleteScheduler["CompleteSystemScheduler"]
    WriteMode --> CompleteScheduler
    AutoMode --> CompleteScheduler
    CompleteScheduler --> Output["TextOutputManager"]
    PeriodMode --> Output
    Output --> File["Output .txt file"]
```

## Use-Case Diagram

```mermaid
flowchart LR
    User["User"]

    User --> UC1["Run period schedule generation"]
    User --> UC2["Count complete yearly systems"]
    User --> UC3["Write complete systems with explicit limit"]
    User --> UC4["Auto-write systems within time limit"]
    User --> UC5["Run tests and validation"]

    UC1 --> System["ExamScheduler"]
    UC2 --> System
    UC3 --> System
    UC4 --> System
    UC5 --> Tests["Pytest suite"]

    System --> Inputs["Course, period, and program files"]
    System --> Output["Schedule output file"]
    Tests --> Validator["Independent schedule validator"]
```

## Class Diagram

```mermaid
classDiagram
    class FileParser {
        +parse_to_json(config) str
    }

    class BaseFactory {
        +build_all(json_str, node_key) list
        _build_one(item_dict)
    }

    class CourseFactory {
        _build_one(course_dict) Course
    }

    class PeriodFactory {
        _build_one(period_dict) ExamPeriod
    }

    class Course {
        +int course_id
        +str name
        +str instructor
        +Evaluation evaluation
        +list affiliations
        +needs_exam_slot() bool
    }

    class ProgramAffiliation {
        +int program_id
        +int year
        +Semester semester
        +RequirementType requirement_type
    }

    class ExamPeriod {
        +Semester semester
        +Term term
        +date start_date
        +date end_date
        +list exclusions
        +is_date_valid(check_date) bool
    }

    class DateExclusion {
        +date start_date
        +date end_date
        +is_date_excluded(check_date) bool
    }

    class AcademicConflictRule {
        +is_valid(attempt_state) bool
    }

    class PeriodScheduler {
        +run_to_output(courses, period, output_manager) int
    }

    class CompleteSystemScheduler {
        +count_complete_systems(period_course_sets) CompleteSystemResult
        +write_complete_systems(period_course_sets, output_manager, max_systems) CompleteSystemResult
        +write_complete_systems_auto(period_course_sets, output_manager, time_limit_seconds) CompleteSystemResult
    }

    class TextOutputManager {
        +get_full_path() Path
        +export(structured_data) str
    }

    class CompleteSystemResult {
        +Path output_path
        +list period_course_counts
        +list period_schedule_counts
        +int complete_system_count
        +int written_system_count
        +float elapsed_seconds
        +bool truncated
    }

    BaseFactory <|-- CourseFactory
    BaseFactory <|-- PeriodFactory
    Course "1" --> "*" ProgramAffiliation
    ExamPeriod "1" --> "*" DateExclusion
    PeriodScheduler --> AcademicConflictRule
    CompleteSystemScheduler --> AcademicConflictRule
    PeriodScheduler --> TextOutputManager
    CompleteSystemScheduler --> TextOutputManager
    CompleteSystemScheduler --> CompleteSystemResult
```

## Sequence: Complete Count Mode

```mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant Workflow as src/workflow.py
    participant Parser as FileParser
    participant Factories as Factories
    participant Scheduler as CompleteSystemScheduler
    participant Rule as AcademicConflictRule

    User->>Main: python main.py --mode complete-count
    Main->>Workflow: run_complete_count_workflow()
    Workflow->>Parser: parse_to_json()
    Parser-->>Workflow: JSON nodes
    Workflow->>Factories: build Course and ExamPeriod objects
    Factories-->>Workflow: domain objects
    Workflow->>Workflow: build_period_course_sets()
    Workflow->>Scheduler: count_complete_systems()
    Scheduler->>Rule: validate same-day conflicts
    Rule-->>Scheduler: valid or invalid
    Scheduler-->>Workflow: CompleteSystemResult
    Workflow-->>Main: result
    Main-->>User: print complete-system count
```

## Sequence: Auto Mode

```mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant Workflow as src/workflow.py
    participant Complete as CompleteSystemScheduler
    participant Output as TextOutputManager

    User->>Main: python main.py --mode auto --time-limit 30
    Main->>Workflow: run_complete_auto_workflow()
    Workflow->>Workflow: load and filter domain data
    Workflow->>Complete: write_complete_systems_auto()
    Complete->>Complete: build period schedule sets
    Complete->>Complete: calculate full product count
    Complete->>Output: open output path
    loop until time budget is almost exhausted
        Complete->>Output: write next complete system
    end
    Complete-->>Workflow: CompleteSystemResult
    Workflow-->>Main: result
    Main-->>User: print count, written systems, elapsed time, truncation
```

## Data Flow

```mermaid
flowchart LR
    CoursesFile["data/V1.0CourseDB.txt"] --> Parser["FileParser"]
    DatesFile["data/V1.0 ExamDates.txt"] --> Parser
    ProgramsFile["data/Programs.txt"] --> Parser

    Parser --> JSON["JSON nodes"]
    JSON --> CourseFactory["CourseFactory"]
    JSON --> PeriodFactory["PeriodFactory"]

    CourseFactory --> Courses["Course objects"]
    PeriodFactory --> Periods["ExamPeriod objects"]
    Courses --> Filter["Filter by selected programs and semester"]
    Periods --> Filter
    Filter --> Solver["Schedulers"]
    Solver --> Result["Counts and output file"]
```

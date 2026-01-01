import json
from agent.modules.fiaetutor import analyze_problem
from agent.modules.fiae_analysis import generate_weakness_report
from agent.modules.planner import prioritize
from agent.modules.career import suggest_path
from agent.memory.memory import init_db, log_fiae_interaction, get_recent_fiae_logs


def handle_fiae():
    print("\n[ FIAE / Algorithmus-Hilfe ]")
    print("Beschreibe deine Aufgabe oder das Problem.")
    print("Gib 'q' ein, um zurück zum Hauptmenü zu gehen.\n")
    problem = input("Problem: ").strip()
    if problem.lower() == "q" or not problem:
        return
    result = analyze_problem(problem)
    result_text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    log_fiae_interaction(problem, result_text)
    print("\n--- Antwort vom FIAE-Modul ---")
    print(result_text)
    print("------------------------------\n")


def handle_fiae_history():
    print("\n[ Verlauf FIAE / Letzte Anfragen ]")
    logs = get_recent_fiae_logs(limit=10)
    if not logs:
        print("Noch keine gespeicherten Einträge.\n")
        return

    for idx, (created_at, problem, answer) in enumerate(logs, start=1):
        print(f"\n#{idx} --- {created_at}")
        print(f"Problem: {problem}")
        print("Antwort (gekürzt):")
        # To keep it compact, only show the first 400 characters
        short_answer = answer[:400]
        print(short_answer)
        if len(answer) > 400:
            print("... [gekürzt]")
    print("\n------------------------------\n")


def handle_fiae_weaknesses():
    print("\n[ Analyse: FIAE-Schwächen & Übungsplan ]")
    print("Analysiere die letzten FIAE-Anfragen und erstelle einen Übungsplan...\n")
    report = generate_weakness_report()
    print("--- Analyse & Trainingsplan ---")
    print(report)
    print("-------------------------------\n")

def handle_planner():
    from agent.modules.planner import Task, Importance, Urgency, prioritize

    print("\n[ Tagesplanung / Eisenhower-Priorisierung ]")
    print("Gib deine Tasks ein, getrennt mit Komma (z.B. 'lernen, einkaufen, Sport').")
    print("Gib nichts ein und drücke Enter, um abzubrechen.\n")
    raw = input("Tasks: ").strip()
    if not raw:
        return

    raw_tasks = [t.strip() for t in raw.split(",") if t.strip()]
    if not raw_tasks:
        print("Keine gültigen Tasks erkannt.\n")
        return

    tasks: list[Task] = []
    print("\nFür jede Aufgabe: ist sie WICHTIG (j/n) und DRINGEND (j/n)?\n")
    for name in raw_tasks:
        print(f"Task: {name}")
        important_answer = input("  Wichtig? (j/n): ").strip().lower()
        urgent_answer = input("  Dringend? (j/n): ").strip().lower()

        importance = Importance.HIGH if important_answer == "j" else Importance.LOW
        urgency = Urgency.HIGH if urgent_answer == "j" else Urgency.LOW

        tasks.append(Task(name=name, importance=importance, urgency=urgency))

    prioritized = prioritize(tasks)

    print("\n--- Ergebnis nach Eisenhower-Matrix ---")

    def print_group(title: str, group: list[Task]):
        print(f"\n{title}:")
        if not group:
            print("  (leer)")
        else:
            for i, t in enumerate(group, start=1):
                print(f"  {i}. {t.name}  [wichtig={t.importance.value}, dringend={t.urgency.value}]")

    print_group("A) SOFORT ERLEDIGEN (wichtig + dringend)", prioritized.do_now)
    print_group("B) EINPLANEN (wichtig + nicht dringend)", prioritized.schedule)
    print_group("C) DELEGIEREN / VEREINFACHEN (nicht wichtig + dringend)", prioritized.delegate)
    print_group("D) STREICHEN / IGNORIEREN (nicht wichtig + nicht dringend)", prioritized.delete)

    print("\n---------------------------------------\n")


def handle_career():
    print("\n[ Karriere / Lernpfad ]")
    print("Gib deine aktuellen Skills ein, getrennt mit Komma (z.B. 'Windows Server, Netzwerk, Python').")
    print("Gib nichts ein und drücke Enter, um abzubrechen.\n")
    raw = input("Skills: ").strip()
    if not raw:
        return
    skills = [s.strip() for s in raw.split(",") if s.strip()]
    suggestions = suggest_path(skills)
    print("\n--- Vorschlag Lern-/Karrierepfad (Platzhalter) ---")
    for i, s in enumerate(suggestions, start=1):
        print(f"{i}. {s}")
    print("-------------------------------------------------\n")


def main():
    init_db()
    print("Barakzai Personal AI Agent v0.1")
    print("Terminal-Modus aktiv.\n")

    while True:
        print("===== Hauptmenü =====")
        print("1) FIAE / Algorithmus-Hilfe")
        print("2) Tagesplanung / Priorisierung")
        print("3) Karriere- & Lernpfad-Beratung")
        print("4) Verlauf: Letzte FIAE-Anfragen")
        print("5) Analyse: FIAE-Schwächen & Übungsplan")
        print("0) Beenden")
        choice = input("Auswahl: ").strip()

        if choice == "0":
            print("Beende Agent. Auf Wiedersehen.")
            break
        elif choice == "1":
            handle_fiae()
        elif choice == "2":
            handle_planner()
        elif choice == "3":
            handle_career()
        elif choice == "4":
            handle_fiae_history()
        elif choice == "5":
            handle_fiae_weaknesses()
        else:
            print("Ungültige Auswahl. Bitte nochmal.\n")


if __name__ == "__main__":
    main()

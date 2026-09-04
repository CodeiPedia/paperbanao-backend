from app.schemas import GeneratePaperRequest

def build_question_prompt(req: GeneratePaperRequest) -> str:
    reqs = []
    if req.mcq.count > 0:
        reqs.append(f"## Multiple Choice Questions [{req.mcq.marks} Mark(s) Each]\n- {req.mcq.count} MCQs (Difficulty: {req.mcq.difficulty}).")
    if req.fib.count > 0:
        reqs.append(f"## Fill in the Blanks [{req.fib.marks} Mark(s) Each]\n- {req.fib.count} questions (Difficulty: {req.fib.difficulty}).")
    if req.true_false.count > 0:
        reqs.append(f"## True/False [{req.true_false.marks} Mark(s) Each]\n- {req.true_false.count} questions (Difficulty: {req.true_false.difficulty}).")
    if req.short_answer.count > 0:
        reqs.append(f"## Short Answer Questions [{req.short_answer.marks} Mark(s) Each]\n- {req.short_answer.count} questions (Difficulty: {req.short_answer.difficulty}).")
    if req.long_answer.count > 0:
        reqs.append(f"## Long Answer Questions [{req.long_answer.marks} Mark(s) Each]\n- {req.long_answer.count} questions (Difficulty: {req.long_answer.difficulty}).")

    answer_key_instr = (
        "\n\nAfter all questions, add a section titled '# ANSWER KEY' with the correct answer for every "
        "question, numbered to match the question numbers."
        if req.include_answer_key else ""
    )

    lang_instr = {
        "Hindi": "Write the entire paper in Hindi (Devanagari script).",
        "Bilingual": "Write each question in both Hindi and English.",
    }.get(req.language, "Write the paper in English.")

    base = (
        f"Subject: {req.subject}, Class: {req.class_name}.\n"
        f"Topics/Chapters: {req.topics or req.subject}\n\n"
        "STRICT SYLLABUS RULE: Every single question must come ONLY from the exact topics/chapters listed "
        "above, at a difficulty and scope appropriate for the stated Class, following the NCERT syllabus for "
        "that class and subject. Do NOT include questions from any other chapter, topic, or grade level — "
        "even ones from the same subject that seem related or commonly paired. If you are unsure whether a "
        "concept belongs to the listed topics/chapters, do not use it. Every question must be traceable to "
        "one of the specific topics/chapters named above.\n\n"
        "COVERAGE: If multiple topics/chapters are listed above, spread the questions as evenly as possible "
        "across ALL of them — do not concentrate most questions on just one or two chapters while barely "
        "touching the others. Every listed chapter should get a fair share of the questions relative to the "
        "total count.\n\n"
        + "\n\n".join(reqs)
        + answer_key_instr
        + f"\n\n{lang_instr}\n\n"
        "DIAGRAMS: For questions about right-angled triangles, circles, or bar-graph statistics, you may "
        "optionally add an accurate diagram by inserting this exact tag on its own line right after the "
        "question text (not in the answer key):\n"
        "[DIAGRAM:triangle|base=4|height=3|base_label=4 cm|height_label=3 cm|hyp_label=?|labels=B,C,A]\n"
        "[DIAGRAM:circle|radius_label=7 cm|center_label=O|point_label=P]\n"
        "[DIAGRAM:bargraph|categories=0-10,10-20,20-30|values=5,12,18|x_label=Marks|y_label=Students]\n"
        "Rules for diagrams: (1) Only add a diagram tag when a right triangle, circle, or bar-graph "
        "statistics visual genuinely fits the question — most questions should have NO diagram at all. "
        "(2) The numbers in the diagram tag MUST exactly match the numbers stated in the question text. "
        "(3) Only use these three types (triangle, circle, bargraph) — never invent other diagram types. "
        "(4) Do not add a diagram to an answer key entry.\n\n"
        "CRITICAL FORMATTING:\n"
        "1. Number ALL questions continuously across all sections (Q1, Q2, Q3...), do not restart per section.\n"
        "2. Use Unicode math symbols (θ, π, √, ²) instead of LaTeX.\n"
        "3. Separate each individual question (and each answer key entry) with the delimiter ||| on its own line.\n"
        "4. Do NOT include a title, institute name, time, or marks header — start directly with the questions."
    )

    if req.source_text.strip():
        base += (
            "\n\nIMPORTANT: CREATE QUESTIONS STRICTLY FROM THE FOLLOWING TEXT EXTRACTED FROM A BOOK:\n\n"
            f"{req.source_text}"
        )

    return base

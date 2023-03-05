"""Code to dynamically generate appropriate LLM prompts."""

from kor.elements import Form, Selection


def _traverse_form(form: Form, depth: int = 0) -> list[tuple[int, str, str, str]]:
    """Traverse a form to generate a type description of its contents."""
    descriptions = [(depth, form.id, "Form", form.description)]
    depth += 1
    for element in form.elements:
        if isinstance(element, Form):
            descriptions.extend(_traverse_form(element, depth + 1))
        else:
            descriptions.append(
                (depth, element.id, element.type_name, element.description)
            )
    return descriptions


def _traverse_form_obj(form: Form, depth: int = 0) -> dict:
    """Traverse a form to generate a type description of its contents."""
    obj = {}
    for element in form.elements:
        if isinstance(element, Form):
            obj.update({element.id: _traverse_form(element)})
        else:
            type_name = element.type_name
            type_name = "String" if type_name == "Text" else type_name
            if isinstance(element, Selection):
                type_name = " | ".join("'" + s.id + "'" for s in element.options)
            obj.update({element.id: type_name})
    return {form.id: obj}


def to_type_script_string(obj, depth: int = 0):
    delimiter = " "
    outer_space = delimiter * depth
    inner_space = delimiter * (depth + 1)
    formatted = [f"{outer_space}" + "{"]
    for key, value in obj.items():
        formatted.append(f"{inner_space}'{key}': {value},")
    formatted.append(f"{outer_space}" + "}")
    return "\n".join(formatted)


def form_to_typestring_type(form: Form) -> str:
    obj = _traverse_form_obj(form)
    return to_type_script_string(obj)


# PUBLIC API


def generate_prompt_for_form(user_input: str, form: Form) -> str:
    """Generate a prompt for a form."""
    inputs_description_block = []
    examples = []
    for element in form.elements:
        inputs_description_block.append(f"* {element.input_full_description}")

        for example_input, example_output in element.llm_examples:
            examples.extend(
                [
                    f"Input: {example_input}",
                    f"Output: <{form.id}>{example_output}</{form.id}>",
                ]
            )

    inputs_description_block = "\n".join(inputs_description_block)
    examples_block = "\n".join(examples).strip()

    return (
        f"You are helping a user fill out a form. The user will type information and your goal "
        f"will be to parse the user's input.\n"
        f'The description of the form is: "{form.description}"'
        "Below is a list of the components showing the component ID, its type and "
        "a short description of it.\n\n"
        f"{inputs_description_block}\n\n"
        "Your task is to parse the user input and determine to what values the user is attempting "
        "to set each component of the form.\n"
        "When the type of the input is a Selection, only output one of the options "
        "specified in the square brackets "
        "as arguments to the Selection type of this input. "
        "Please enclose the extracted information in HTML style tags with the tag name "
        "corresponding to the corresponding component ID. Use angle style brackets for the "
        "tags ('>' and '<'). "
        "Only output tags when you're confident about the information that was extracted "
        "from the user's query. If you can extract several pieces of relevant information "
        'from the query include use a comma to separate the tags. If "Multiple" is part '
        "of the component's type, then please repeat the same tag multiple times once for "
        'each relevant extraction. If the type does not contain "Multiple" do not include it '
        "more than once."
        "\n\n"
        f"{examples_block}\n"
        f"Input: {user_input}\n"
        "Output: "
    )


def generate_chat_prompt_for_form(user_input: str, form: Form) -> list[dict]:
    """Generate a prompt for a form."""

    # Generate system message which contains instructions.
    descriptions = _traverse_form(form)
    # form_description_block = "\n".join(
    #     [
    #         "{space}* <{id}>: {type} ({description})".format(
    #             space="  " * depth, id=id, type=type, description=description
    #         )
    #         for depth, id, type, description in descriptions
    #     ]
    # )
    form_description_block = form_to_typestring_type(form)
    system_message = {
        "role": "system",
        "content": (
            "Your goal is to extract structured information from the user's input that matches "
            f"the form described below. The form description is specified in type string "
            f"for each component. The description is hierarchical starting with the form itself."
            f"\n\n"
            f"{form_description_block}\n\n"
            "Please enclose the extracted information in HTML style tags with the tag name "
            "corresponding to the corresponding component ID. Use angle style brackets for the "
            "tags ('>' and '<'). "
            "Only output tags when you're confident about the information that was extracted "
            "from the user's query. If you can extract several pieces of relevant information "
            'from the query, then include all of them. If "Multiple" is part '
            "of the component's type, please repeat the same tag multiple times once for "
            'each relevant extraction. If the type does not contain "Multiple" do not include it '
            "more than once."
        ),
    }

    messages = [system_message]

    # Add user assistant messages
    for element in form.elements:
        for example_input, example_output in element.llm_examples:
            messages.extend(
                [
                    {"role": "user", "content": example_input},
                    {
                        "role": "assistant",
                        "content": f"<{form.id}>{example_output}</{form.id}>",
                    },
                ]
            )

    messages.append({"role": "user", "content": user_input})
    return messages

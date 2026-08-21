AI_PRM_EMOJIES = {
    "EXITED" : {"t" : '<tg-emoji emoji-id="5237764698245450016">😊</tg-emoji>' , "d" : "هیجان زده"},
    "CONFIRM" : {"t" : '<tg-emoji emoji-id="5238224229681350693">😊</tg-emoji>' , "d" : "مشتاق و حالت تایید"},
    "EMBARRASSED" : {"t" : '<tg-emoji emoji-id="5240300936563278060">😊</tg-emoji>' , "d" : "خجالت زده و ناراحت از کار فرد"},
    "ANGERY" : {"t" : '<tg-emoji emoji-id="5240021540350740642">😊</tg-emoji>' , "d" : "عصبانیت با خجالت"},
    "REJECT" : {"t" : '<tg-emoji emoji-id="5238041302729247271">😊</tg-emoji>' , "d" : "رد نکردن _ قبول نکردن"},
    "LAUGHING" : {"t" : '<tg-emoji emoji-id="5239948852324221211">😊</tg-emoji>' , "d" : "از ته دل خندیدن"},
}

def get_ai_prm_emojies_list(emojis=None):
    """Build the AI-facing tag list from a mapping or database-like rows."""
    source = emojis or AI_PRM_EMOJIES
    if isinstance(source, dict):
        return "".join(f"{key} = {value['d']}\n" for key, value in source.items())
    return "".join(
        f"{item['tag']} = {item['description']}\n"
        for item in source
    )


def place_ai_prm_emojies(text: str, emojis=None):
    new_text = text
    source = emojis or AI_PRM_EMOJIES
    items = (
        ({"tag": key, "text": value["t"]} for key, value in source.items())
        if isinstance(source, dict)
        else source
    )
    for item in items:
        tag = str(item.get("tag") or "")
        replacement = item.get("text") or (
            f'<tg-emoji emoji-id="{item["emoji_id"]}">😊</tg-emoji>'
        )
        if not tag:
            continue
        new_text = new_text.replace(tag, replacement)
    return new_text

if __name__ == "__main__":
    text = get_ai_prm_emojies_list()
    print(place_ai_prm_emojies(text=text))


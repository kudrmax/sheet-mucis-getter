from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

CHOOSE_SHEETS = "Выбрать ноты"
UPLOAD_SHEETS = "Загрузить ноты"
CIFROVKI = "Цифровки"


def get_start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CHOOSE_SHEETS), KeyboardButton(text=UPLOAD_SHEETS)],
            [KeyboardButton(text=CIFROVKI)],
        ],
        resize_keyboard=True,
    )


NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def get_folders_inline_keyboard(
    folders: list[dict], selected_ids: list[str]
) -> InlineKeyboardMarkup:
    use_numbers = len(selected_ids) >= 2
    buttons = []
    for folder in folders:
        if folder["id"] in selected_ids:
            if use_numbers:
                idx = selected_ids.index(folder["id"])
                mark = NUMBER_EMOJI[idx] if idx < len(NUMBER_EMOJI) else f"({idx + 1})"
            else:
                mark = "\u2705"
        else:
            mark = "\u2b1c"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {folder['name']}",
                    callback_data=f"folder_toggle:{folder['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text="Выбрать все", callback_data="select_all"),
            InlineKeyboardButton(
                text="Скачать выбранные", callback_data="download_selected"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_upload_folders_inline_keyboard(
    folders: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []
    for folder in folders:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=folder["name"],
                    callback_data=f"upload_folder:{folder['id']}:{folder['name']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Создать папку", callback_data="create_upload_folder"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_filename_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить", callback_data="confirm_filename"
                ),
                InlineKeyboardButton(
                    text="Переименовать", callback_data="rename_filename"
                ),
            ]
        ]
    )


def get_more_files_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Загрузить ещё", callback_data="upload_more"
                ),
                InlineKeyboardButton(text="Готово", callback_data="upload_done"),
            ]
        ]
    )


# ── Cifrovka keyboards ──


def get_cifrovka_folder_keyboard(
    folders: list[dict],
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f["name"], callback_data=f"cif_f:{i}")]
        for i, f in enumerate(folders)
    ]
    buttons.append(
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="cif_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cifrovka_view_keyboard(
    current_idx: int, total: int, *, is_pinned: bool = False,
) -> InlineKeyboardMarkup:
    rows = []

    # Navigation row (only if more than 1 version)
    if total > 1:
        nav_row = []
        if current_idx > 0:
            nav_row.append(InlineKeyboardButton(text="\u25c0\ufe0f", callback_data="cif_prev"))
        nav_row.append(
            InlineKeyboardButton(text=f"{current_idx + 1}/{total}", callback_data="cif_noop")
        )
        if current_idx < total - 1:
            nav_row.append(InlineKeyboardButton(text="\u25b6\ufe0f", callback_data="cif_next"))
        rows.append(nav_row)

    # Action row
    action_row = [
        InlineKeyboardButton(text="\u270f\ufe0f", callback_data="cif_edit"),
        InlineKeyboardButton(text="\U0001f5d1", callback_data="cif_delete"),
        InlineKeyboardButton(text="\u2795", callback_data="cif_new"),
    ]
    if total > 1:
        pin_text = "\U0001f4cc" if is_pinned else "\U0001f4cd"
        action_row.append(InlineKeyboardButton(text=pin_text, callback_data="cif_pin"))
    rows.append(action_row)

    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="cif_back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_cifrovka_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\u2795 Создать", callback_data="cif_new")],
            [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="cif_back")],
        ]
    )


def get_cifrovka_delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f5d1 Да, удалить", callback_data="cif_del_yes"),
                InlineKeyboardButton(text="Отмена", callback_data="cif_del_no"),
            ]
        ]
    )

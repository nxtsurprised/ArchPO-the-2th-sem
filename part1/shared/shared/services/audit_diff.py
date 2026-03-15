from __future__ import annotations


def compute_changes(old: dict, new: dict) -> dict | None:
    """
    Вычисляет разницу между двумя состояниями объекта для аудит-лога.

    Используется перед сохранением обновлённой записи: берём старый dict,
    новый dict, получаем только изменившиеся поля.

    Пример:
        old = {"labor_hours": 120, "status": "draft"}
        new = {"labor_hours": 80,  "status": "draft"}
        -> {"labor_hours": {"old": 120, "new": 80}}

    Возвращает None вместо пустого dict, чтобы упростить проверки
    в вызывающем коде (if changes: ...).
    """
    changes = {}

    # Объединяем ключи обоих dict – учитываем как изменения значений,
    # так и добавление/удаление полей
    all_keys = set(old.keys()) | set(new.keys())

    for key in all_keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}

    return changes if changes else None

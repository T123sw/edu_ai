"""Answer-free progress based on emitted question slots, including replay."""


def question_progress(event):
    metadata = event.get('metadata') or {}
    if event.get('type') != 'content' or metadata.get('call_kind') != 'quiz_question_emitted':
        return None
    index, total = metadata.get('question_index'), metadata.get('total_questions')
    if type(index) is not int or type(total) is not int or not 0 <= index < total:
        return None
    return {'processed': index + 1, 'total': total}


def question_status(value):
    processed, total = value['processed'], value['total']
    percent = 40 + (55 * processed // total)
    message = f'已处理 {processed}/{total} 题'
    if processed < total:
        message += f'，正在生成第 {processed + 1} 题'
    else:
        message += '，正在保存试卷'
    return percent, 'quizzing', message

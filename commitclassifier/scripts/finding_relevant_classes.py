
def splitter(diff):
    return diff.split('\n')[0].replace('diff --git a/', '').split(' ')[0]


def find_relevant_java_class(diff_file, java_files):

    diff_path = splitter(diff_file)

    for file in java_files:
        path = file.metadata['file_path']
        if path == diff_path:
            return file.page_content

    class_name = diff_path.split('/')[-1]
    for file in java_files:
        java_class = file.metadata['file_path'].split('/')[-1]
        if java_class == class_name:
            return file.page_content

    return ''


def find_called_class(diff_file, java_files):

    diff_class = splitter(diff_file).split('/')[-1].replace('.java', '')

    for file in java_files:
        content = file.page_content
        if diff_class in content:
                return content

    return ''

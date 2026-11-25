from pathlib import Path

from ..errors import NpiError


def one_file(folder, pattern):
    """資料夾裡要剛好一份符合的檔案，否則報錯並指出資料夾。"""
    folder = Path(folder)
    files = sorted(folder.glob(pattern)) if folder.is_dir() else []
    if len(files) != 1:
        raise NpiError(f"{folder}：要剛好一份 {pattern}，現在有 {len(files)} 份")
    return files[0]

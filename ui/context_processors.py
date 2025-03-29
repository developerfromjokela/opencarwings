import os

from git import Repo

from tculink import VERSION

repo = Repo(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
commit_hash = repo.git.rev_parse("HEAD")


def load_ver_info(request):
    return {'appinfo': {"version": VERSION, "commit": commit_hash[:7]}}
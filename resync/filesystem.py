import os
from stat import S_ISREG, S_ISDIR
import logging

logger = logging.getLogger(__name__)


class SshFileSystem:
    '''An SSH client to interact with the remakable filesystem.'''

    def __init__(self, ssh_client, root_dir=None):

        self.sftp = ssh_client.open_sftp()

        if root_dir is None:
            root_dir = '/'
        self.root_dir = root_dir

    def put_file(self, local, remote, overwrite=False):
        '''Copy file ``local`` to ``remote`` (relative to document root)'''

        path = self.__to_remote_path(remote)

        if overwrite or not self.__is_file(path):
            self.sftp.put(local, path)
            return True

        return False

    def get_file(self, remote, local, overwrite=False):
        '''Copy file ``remote`` (relative to document root) to ``local``'''

        path = self.__to_remote_path(remote)

        if overwrite or not os.path.exists(local):
            self.sftp.get(path, local)
            return True

        return False

    def read_file(self, remote):
        '''Read file ``remote`` (relative to document root).'''

        path = self.__to_remote_path(remote)

        content = ""
        for line in self.sftp.open(path, 'r'):
            content += line

        return content

    def write_file(self, content, remote, overwrite=False):
        '''Create file ``remote`` (relative to document root) with the given
        content.'''

        path = self.__to_remote_path(remote)

        if overwrite or not self.__is_file(path):
            try:
                with self.sftp.open(path, 'w') as f:
                    f.write(content)
            except Exception:
                logger.error("Could not open %s for writing", path)
                raise
            return True

        logger.error("File %s already exists, not overwriting it", path)
        return False

    def make_dir(self, remote):
        '''Create the directory ``remote``.'''

        path = self.__to_remote_path(remote)

        try:
            self.sftp.mkdir(path)
            return True
        except Exception:
            return False

    def exists(self, remote):
        '''Check if ``remote`` is a file.'''

        path = self.__to_remote_path(remote)

        return self.__is_file(path)

    def list(self, remote):
        '''List all entries in ``remote``.'''

        path = self.__to_remote_path(remote)
        return list(self.sftp.listdir(path))

    def __to_remote_path(self, path):
        return os.path.join(self.root_dir, path.lstrip('/'))

    def __is_file(self, path):

        try:
            p = self.sftp.stat(path)
        except Exception:
            return False
        return S_ISREG(p.st_mode) != 0

    def __is_dir(self, path):

        try:
            p = self.sftp.stat(path)
        except Exception:
            return False
        return S_ISDIR(p.st_mode) != 0

import logging
import paramiko
from .filesystem import SshFileSystem
from .store import RemarkableStore
from .render import render_document
from .entries import Pdf, Notebook


logger = logging.getLogger(__name__)


class RemarkableClient:
    """Client to access documents and their associated PDF data."""

    document_root = "/home/root/.local/share/remarkable/xochitl"
    restart_command = "/bin/systemctl restart xochitl"

    def __init__(self, address, username="root", document_root=None):
        self.ssh_client = None
        self.__connect(address, username)

        if document_root is not None:
            self.document_root = document_root

        self.fs = SshFileSystem(self.ssh_client, self.document_root)
        self.store = RemarkableStore(self.fs)

    def restart(self):
        """Restart ``xochitl`` (the GUI) on the remarkable.

        This is necessary to see changes made to the document tree.
        """
        _, out, _ = self.ssh_client.exec_command(self.restart_command)
        if out.channel.recv_exit_status() != 0:
            logger.error("Could not restart xochitl")

    def get_pdf(self, document):
        """Get PDF data associated with a document."""
        logger.debug("[RemarkableClient::get_pdf] %s", document)

        if not (isinstance(document, Pdf) or isinstance(document, Notebook)):
            raise NotImplementedError(
                "Reading entries other than Notebook or Pdf not yet implemented"
            )

        return render_document(document)

    def put_pdf(self, pdf_data, folder=None, name=None, document=None):
        """Set the PDF data of a document.

        This either creates a new PDF document in the given folder and name or
        replaces the PDF of an existing document.

        Returns the (newly created) document.
        """
        assert document is not None or (folder is not None and name is not None)

        if document is None:
            assert folder is not None and name is not None
            document = self.store.create(folder, name, Pdf)
        else:
            assert folder is None and name is None
            if not isinstance(document, Pdf):
                raise NotImplementedError(
                    "Writing entries other than Pdf not yet implemented"
                )

        self.fs.write_file(pdf_data, document.uid + ".pdf")
        self.fs.write_file("", document.uid + ".pagedata")
        self.fs.make_dir(document.uid)

        return document

    def __connect(self, address, username):
        logger.info("Connecting to %s...", address)

        if self.ssh_client is not None:
            logger.error("Already connected")
            return

        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.connect(address, username=username, look_for_keys=True)

        logger.info("...connected.")
        self.ssh_client = ssh_client

    def __disconnect(self):
        self.ssh_client.close()
        self.ssh_client = None

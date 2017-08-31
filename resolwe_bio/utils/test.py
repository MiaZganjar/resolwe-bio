"""Test helper functions."""
import os
import unittest
import sys

import wrapt

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase as DjangoTestCase

from resolwe.test import with_resolwe_host as resolwe_with_resolwe_host, TransactionProcessTestCase

TEST_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tests', 'files'))
TEST_LARGE_FILES_DIR = os.path.join(TEST_FILES_DIR, 'large')


def skipDockerFailure(reason):  # pylint: disable=invalid-name
    """Skip decorated tests due to failures when run in Docker.

    Unless ``TESTS_SKIP_DOCKER_FAILURES`` Django setting is set to
    ``False``. ``reason`` should describe why the test is being skipped.
    """
    if getattr(settings, 'TESTS_SKIP_DOCKER_FAILURES', True):
        return unittest.skip(reason)
    return lambda func: func


def skipUnlessLargeFiles(*files):  # pylint: disable=invalid-name
    r"""Skip decorated tests unless large files are available.

    :param list \*files: variable lenght files list, where each element
                         represents a large file path relative to the
                         ``TEST_LARGE_FILES_DIR`` directory

    """
    for file_ in files:
        file_path = os.path.join(TEST_LARGE_FILES_DIR, file_)
        if not os.path.isfile(file_path):
            return unittest.skip("File '{}' is not available".format(file_path))
        try:
            with open(file_path) as f:
                if f.readline().startswith('version https://git-lfs.github.com/spec/'):
                    return unittest.skip("Only Git LFS pointer is available "
                                         "for file '{}'".format(file_path))
        except UnicodeDecodeError:
            # file_ is a binary file (this is expected)
            pass
    return lambda func: func


@wrapt.decorator
def with_resolwe_host(wrapped_method, instance, args, kwargs):
    """Decorate unit test to give it access to a live Resolwe host.

    This is a slightly modified version of Resolwe's
    :func:`~resolwe.test.utils.with_resolwe_host` decorator which skips
    the decorated tests on non-Linux systems since accessing live
    Resolwe host from a Docker container on non-Linux systems is not
    possible yet.

    """
    return unittest.skipUnless(
        sys.platform.startswith('linux'),
        "Accessing live Resolwe host from a Docker container on non-Linux systems is not possible "
        "yet."
    )(resolwe_with_resolwe_host)(wrapped_method)(*args, **kwargs)


class TransactionBioProcessTestCase(TransactionProcessTestCase):
    """Base class for writing bioinformatics process tests not enclosed in a transaction.

    It is a subclass of Resolwe's
    :class:`~resolwe.test.TransactionProcessTestCase` with some specific
    functions used for testing bioinformatics processes.

    It is useful when one needs access to the process test's database
    from another thread/process.

    """

    def setUp(self):
        """Initialize test files path."""
        super(TransactionBioProcessTestCase, self).setUp()
        self.files_path = TEST_FILES_DIR

    def prepare_genome(self):
        """Prepare genome FASTA."""
        inputs = {"src": "genome.fasta.gz",
                  "bowtie_index": "bt_index.tar.gz",
                  "bowtie2_index": "bt2_index.tar.gz",
                  "bwa_index": "bwa_index.tar.gz",
                  "hisat2_index": "hisat2_index.tar.gz",
                  "subread_index": "subread_index.tar.gz"}
        return self.run_process('upload-genome', inputs)

    def prepare_reads(self, fn=['reads.fastq.gz']):
        """Prepare NGS reads FASTQ."""
        inputs = {'src': fn}
        return self.run_process('upload-fastq-single', inputs)

    def prepare_paired_reads(self, mate1=['fw_reads.fastq.gz'], mate2=['rw_reads.fastq.gz']):
        """Prepare NGS reads FASTQ."""
        inputs = {'src1': mate1, 'src2': mate2}
        return self.run_process('upload-fastq-paired', inputs)

    def prepare_bam(self, fn='sp_test.bam'):
        """Prepare alignment BAM."""
        inputs = {'src': fn}
        return self.run_process('upload-bam', inputs)

    def prepare_annotation(self, fn='sp_test.gtf', source='DICTYBASE'):
        """Prepare annotation GTF."""
        inputs = {'src': fn, 'source': source}
        return self.run_process('upload-gtf', inputs)

    def prepare_adapters(self, fn='adapters.fasta'):
        """Prepare adapters FASTA."""
        return self.run_process('upload-fasta-nucl', {'src': fn})

    def prepare_expression(self, f_rc='exp_1_rc.tab.gz',
                           f_exp='exp_1_tpm.tab.gz',
                           f_type="TPM",
                           name='Expression',
                           source='DICTYBASE'):
        """Prepare expression."""
        inputs = {'rc': f_rc, 'exp': f_exp, 'exp_type': f_type, 'exp_name': name, 'source': source}
        return self.run_process('upload-expression', inputs)

    def prepare_amplicon_master_file(self, mfile='56G_masterfile_test.txt', pname='56G panel, v2'):
        """Prepare amplicon master file."""
        return self.run_process('upload-master-file', {'src': mfile, 'panel_name': pname})


class BioProcessTestCase(TransactionBioProcessTestCase, DjangoTestCase):
    """Base class for writing bioinformatics process tests.

    It is based on :class:`~.TransactionBioProcessTestCase` and
    Django's :class:`~django.test.TestCase`.
    The latter encloses the test code in a database transaction that is
    rolled back at the end of the test.

    """

    pass


class KBBioProcessTestCase(BioProcessTestCase):
    """Test class for bioinformatics processes that uses knowledge base."""

    def setUp(self):
        """Set-up test gene information knowledge base."""
        super(KBBioProcessTestCase, self).setUp()
        call_command('insert_features', os.path.join(TEST_FILES_DIR, 'features_gsea.tab.zip'))
        call_command('insert_mappings', os.path.join(TEST_FILES_DIR, 'mappings_gsea.tab.zip'))

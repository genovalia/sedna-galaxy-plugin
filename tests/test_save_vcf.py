"""Unit tests for sedna_fetch.save_vcf: a gzip download is written as plain VCF text."""

import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sedna_fetch  # noqa: E402

VCF = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n1\t10\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"


class FakeResponse:
    def __init__(self, body, disposition=None):
        self.body = body
        self.headers = {"Content-Disposition": disposition} if disposition else {}

    def iter_content(self, chunk_size):
        for i in range(0, len(self.body), 7):  # small chunks, like a stream
            yield self.body[i:i + 7]


def test_a_gz_download_is_written_as_plain_vcf(tmp_path):
    out = tmp_path / "out.vcf"
    response = FakeResponse(gzip.compress(VCF), 'attachment; filename="ds_1.vcf.gz"')

    sedna_fetch.save_vcf(response, str(out))

    assert out.read_bytes() == VCF


def test_a_plain_download_is_written_as_it_is(tmp_path):
    out = tmp_path / "out.vcf"
    response = FakeResponse(VCF, 'attachment; filename="ds_1.vcf"')

    sedna_fetch.save_vcf(response, str(out))

    assert out.read_bytes() == VCF


def test_without_a_name_the_gzip_magic_bytes_decide(tmp_path):
    out = tmp_path / "out.vcf"

    sedna_fetch.save_vcf(FakeResponse(gzip.compress(VCF)), str(out))

    assert out.read_bytes() == VCF


def test_a_multi_member_bgzf_download_is_decompressed_entirely(tmp_path):
    # BGZF is a series of gzip members: every one must be read
    out = tmp_path / "out.vcf"
    body = gzip.compress(VCF[:40]) + gzip.compress(VCF[40:])
    response = FakeResponse(body, 'attachment; filename="ds_1.vcf.gz"')

    sedna_fetch.save_vcf(response, str(out))

    assert out.read_bytes() == VCF

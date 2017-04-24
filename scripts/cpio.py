#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Script to parse copy in and out (CPIO) archive files."""

from __future__ import print_function
import argparse
import bz2
import gzip
import hashlib
import logging
import os
import sys

import lzma

from dtformats import cpio


class CPIOArchiveFileHasher(object):
  """CPIO archive file hasher."""

  _BZIP_SIGNATURE = b'BZ'
  _CPIO_SIGNATURE_BINARY_BIG_ENDIAN = b'\x71\xc7'
  _CPIO_SIGNATURE_BINARY_LITTLE_ENDIAN = b'\xc7\x71'
  _CPIO_SIGNATURE_PORTABLE_ASCII = b'070707'
  _CPIO_SIGNATURE_NEW_ASCII = b'070701'
  _CPIO_SIGNATURE_NEW_ASCII_WITH_CHECKSUM = b'070702'
  _GZIP_SIGNATURE = b'\x1f\x8b'
  _XZ_SIGNATURE = b'\xfd7zXZ\x00'

  def __init__(self, path, debug=False):
    """Initializes the CPIO archive file hasher object.

    Args:
      path (str): path of the CPIO archive file.
      debug (Optional[bool]): True if debug information should be printed.
    """
    super(CPIOArchiveFileHasher, self).__init__()
    self._debug = debug
    self._path = path

  def HashFileEntries(self, output_writer):
    """Hashes the file entries stored in the CPIO archive file.

    Args:
      output_writer (OutputWriter): output writer.
    """
    stat_object = os.stat(self._path)

    file_object = open(self._path, 'rb')

    file_offset = 0
    file_size = stat_object.st_size

    # initrd files can consist of an uncompressed and compressed cpio archive.
    # Keeping the functionality in this script for now, but this likely
    # needs to be in a separate initrd hashing script.
    while file_offset < stat_object.st_size:
      file_object.seek(file_offset, os.SEEK_SET)
      signature_data = file_object.read(6)

      file_type = None
      if len(signature_data) > 2:
        if (signature_data[:2] in (
            self._CPIO_SIGNATURE_BINARY_BIG_ENDIAN,
            self._CPIO_SIGNATURE_BINARY_LITTLE_ENDIAN) or
            signature_data in (
                self._CPIO_SIGNATURE_PORTABLE_ASCII,
                self._CPIO_SIGNATURE_NEW_ASCII,
                self._CPIO_SIGNATURE_NEW_ASCII_WITH_CHECKSUM)):
          file_type = u'cpio'
        elif signature_data[:2] == self._GZIP_SIGNATURE:
          file_type = u'gzip'
        elif signature_data[:2] == self._BZIP_SIGNATURE:
          file_type = u'bzip'
        elif signature_data == self._XZ_SIGNATURE:
          file_type = u'xz'

      if not file_type:
        output_writer.WriteText(
            u'Unsupported file type at offset: 0x{0:08x}.'.format(file_offset))
        return

      if file_type == u'cpio':
        file_object.seek(file_offset, os.SEEK_SET)
        cpio_file_object = file_object
      elif file_type in (u'bzip', u'gzip', u'xz'):
        compressed_data_file_object = cpio.DataRange(file_object)
        compressed_data_file_object.SetRange(
            file_offset, file_size - file_offset)

        if file_type == u'bzip':
          cpio_file_object = bz2.BZ2File(compressed_data_file_object)
        elif file_type == u'gzip':
          cpio_file_object = gzip.GzipFile(fileobj=compressed_data_file_object)
        elif file_type == u'xz':
          cpio_file_object = lzma.LZMAFile(compressed_data_file_object)

      cpio_archive_file = cpio.CPIOArchiveFile(debug=self._debug)
      cpio_archive_file.ReadFileObject(cpio_file_object)

      for file_entry in sorted(cpio_archive_file.GetFileEntries()):
        if file_entry.data_size == 0:
          continue

        sha256_context = hashlib.sha256()
        file_data = file_entry.read(4096)
        while file_data:
          sha256_context.update(file_data)
          file_data = file_entry.read(4096)

        output_writer.WriteText(u'{0:s}\t{1:s}'.format(
            sha256_context.hexdigest(), file_entry.path))

      file_offset += cpio_archive_file.size

      padding_size = file_offset %  16
      if padding_size > 0:
        file_offset += 16 - padding_size

      cpio_archive_file.Close()


class StdoutWriter(object):
  """Stdout output writer."""

  def Close(self):
    """Closes the output writer object."""
    return

  def Open(self):
    """Opens the output writer object.

    Returns:
      bool: True if successful or False if not.
    """
    return True

  def WriteText(self, text):
    """Writes text to stdout.

    Args:
      text (str): text to write.
    """
    print(text)


def Main():
  """The main program function.

  Returns:
    bool: True if successful or False if not.
  """
  argument_parser = argparse.ArgumentParser(description=(
      u'Extracts information from CPIO archive files.'))

  argument_parser.add_argument(
      u'-d', u'--debug', dest=u'debug', action=u'store_true', default=False,
      help=u'enable debug output.')

  argument_parser.add_argument(
      u'--hash', dest=u'hash', action=u'store_true', default=False,
      help=u'calculate the SHA-256 sum of the file entries.')

  argument_parser.add_argument(
      u'source', nargs=u'?', action=u'store', metavar=u'PATH',
      default=None, help=u'path of the CPIO archive file.')

  options = argument_parser.parse_args()

  if not options.source:
    print(u'Source file missing.')
    print(u'')
    argument_parser.print_help()
    print(u'')
    return False

  logging.basicConfig(
      level=logging.INFO, format=u'[%(levelname)s] %(message)s')

  output_writer = StdoutWriter()

  if not output_writer.Open():
    print(u'Unable to open output writer.')
    print(u'')
    return False

  if options.hash:
    cpio_archive_file_hasher = CPIOArchiveFileHasher(
        options.source, debug=options.debug)

    cpio_archive_file_hasher.HashFileEntries(output_writer)

  else:
    # TODO: move functionality to CPIOArchiveFileInfo.
    cpio_archive_file = cpio.CPIOArchiveFile(debug=options.debug)
    cpio_archive_file.Open(options.source)

    output_writer.WriteText(u'CPIO archive information:')
    output_writer.WriteText(u'\tFormat\t\t: {0:s}'.format(
        cpio_archive_file.file_format))
    output_writer.WriteText(u'\tSize\t\t: {0:d} bytes'.format(
        cpio_archive_file.size))

    cpio_archive_file.Close()

  output_writer.WriteText(u'')
  output_writer.Close()

  return True


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)
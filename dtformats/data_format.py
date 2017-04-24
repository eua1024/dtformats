# -*- coding: utf-8 -*-
"""Binary data format."""

from __future__ import print_function
import abc
import os

from dtfabric import errors as dtfabric_errors

import errors


class BinaryDataFormat(object):
  """Binary data format."""

  _HEXDUMP_CHARACTER_MAP = [
      '.' if byte < 0x20 or byte > 0x7e else chr(byte) for byte in range(256)]

  def __init__(self, debug=False):
    """Initializes a binary data format.

    Args:
      debug (Optional[bool]): True if debug information should be printed.
    """
    super(BinaryDataFormat, self).__init__()
    self._debug = debug

  def _DebugPrintData(self, description, data):
    """Prints data debug information.

    Args:
      description (str): description.
      data (bytes): data.
    """
    print(u'{0:s}:'.format(description))
    print(self.FormatDataInHexadecimal(data))

  def _DebugPrintValue(self, description, value):
    """Prints a value debug information.

    Args:
      description (str): description.
      value (object): value.
    """
    alignment, _ = divmod(len(description), 8)
    alignment = 8 - alignment + 1
    text = u'{0:s}{1:s}: {2!s}'.format(description, u'\t' * alignment, value)
    print(text)

  def FormatDataInHexadecimal(self, data):
    """Formats data in a hexadecimal represenation.

    Args:
      data (bytes): data.

    Returns:
      str: hexadecimal represenation of the data.
    """
    in_group = False
    previous_hexadecimal_string = None

    lines = []
    data_size = len(data)
    for block_index in xrange(0, data_size, 16):
      data_string = data[block_index:block_index + 16]

      hexadecimal_string1 = ' '.join([
          u'{0:02x}'.format(ord(byte_value))
          for byte_value in data_string[0:8]])
      hexadecimal_string2 = ' '.join([
          u'{0:02x}'.format(ord(byte_value))
          for byte_value in data_string[8:16]])

      printable_string = u''.join([
          self._HEXDUMP_CHARACTER_MAP[
              ord(byte_value)] for byte_value in data_string])

      remaining_size = 16 - len(data_string)
      if remaining_size == 0:
        whitespace = u''
      elif remaining_size >= 8:
        whitespace = ' ' * ((3 * remaining_size) - 1)
      else:
        whitespace = ' ' * (3 * remaining_size)

      hexadecimal_string = u'{0:s}  {1:s}{2:s}'.format(
          hexadecimal_string1, hexadecimal_string2, whitespace)

      if (previous_hexadecimal_string is not None and
          previous_hexadecimal_string == hexadecimal_string and
          block_index + 16 < data_size):

        if not in_group:
          in_group = True

          lines.append('...')

      else:
        lines.append(u'0x{0:08x}  {1:s}  {2:s}'.format(
            block_index, hexadecimal_string, printable_string))

        in_group = False
        previous_hexadecimal_string = hexadecimal_string

    lines.append(u'')
    return u'\n'.join(lines)

  def _ReadStructure(
      self, file_object, file_offset, data_size, data_type_map, description):
    """Reads a structure.

    Args:
      file_object (file): a file-like object.
      file_offset (int): offset of the data relative from the start of
          the file-like object.
      data_size (int): data size of the structure.
      data_type_map (dtfabric.DataTypeMap): data type map of the structure.
      description (str): description of the structure.

    Returns:
      object: structure values object.

    Raises:
      ParseError: if the structure cannot be read.
    """
    file_object.seek(file_offset, os.SEEK_SET)

    if self._debug:
      print(u'Reading {0:s} at offset: 0x{1:08x}'.format(
          description, file_offset))

    try:
      data = file_object.read(data_size)
    except IOError as exception:
      raise errors.ParseError((
          u'Unable to read {0:s} data at offset: 0x{1:08x} with error: '
          u'{2:s}').format(description, file_offset, exception))

    if len(data) != data_size:
      raise errors.ParseError((
          u'Unable to read {0:s} data at offset: 0x{1:08x} with error: '
          u'missing data').format(description, file_offset))

    if self._debug:
      data_description = u'{0:s} data'.format(description.title())
      self._DebugPrintData(data_description, data)

    try:
      return data_type_map.MapByteStream(data)
    except dtfabric_errors.MappingError as exception:
      raise errors.ParseError((
          u'Unable to read {0:s} at offset: 0x{1:08x} with error: '
          u'{2:s}').format(description, file_offset, exception))


class BinaryDataFile(BinaryDataFormat):
  """Binary data file."""

  def __init__(self, debug=False):
    """Initializes a binary data file.

    Args:
      debug (Optional[bool]): True if debug information should be printed.
    """
    super(BinaryDataFile, self).__init__(debug=debug)
    self._file_object = None
    self._file_object_opened_in_object = False
    self._file_size = 0

  def Close(self):
    """Closes a binary data file.

    Raises:
      IOError: if the file is not opened.
    """
    if not self._file_object:
      raise IOError(u'File not opened')

    if self._file_object_opened_in_object:
      self._file_object.close()
      self._file_object_opened_in_object = False
    self._file_object = None

  def Open(self, path):
    """Opens a binary data file.

    Args:
      path (str): path to the file.

    Raises:
      IOError: if the file is already opened.
    """
    if self._file_object:
      raise IOError(u'File already opened')

    stat_object = os.stat(path)

    file_object = open(path, 'rb')

    self._file_size = stat_object.st_size

    self.ReadFileObject(file_object)

    self._file_object = file_object
    self._file_object_opened_in_object = True

  @abc.abstractmethod
  def ReadFileObject(self, file_object):
    """Reads binary data from a file-like object.

    Args:
      file_object (file): file-like object.
    """
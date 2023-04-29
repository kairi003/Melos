# This implementation has been ported from discord.py==1.7.3

import subprocess
import shlex

from discord.errors import ClientException
from discord.opus import Encoder as OpusEncoder

from discord.player import AudioSource, CREATE_NO_WINDOW
from discord.player import _log as log


class FFmpegAudio(AudioSource):
    """Represents an FFmpeg (or AVConv) based AudioSource.

    User created AudioSources using FFmpeg differently from how :class:`FFmpegPCMAudio` and
    :class:`FFmpegOpusAudio` work should subclass this.

    .. versionadded:: 1.3
    """

    def __init__(self, source, *, executable='ffmpeg', args, **subprocess_kwargs):
        self._process = self._stdout = None

        args = [executable, *args]
        kwargs = {'stdout': subprocess.PIPE}
        kwargs.update(subprocess_kwargs)

        self._process = self._spawn_process(args, **kwargs)
        self._stdout = self._process.stdout

    def _spawn_process(self, args, **subprocess_kwargs):
        process = None
        try:
            process = subprocess.Popen(args, creationflags=CREATE_NO_WINDOW, **subprocess_kwargs)
        except FileNotFoundError:
            executable = args.partition(' ')[0] if isinstance(args, str) else args[0]
            raise ClientException(executable + ' was not found.') from None
        except subprocess.SubprocessError as exc:
            raise ClientException('Popen failed: {0.__class__.__name__}: {0}'.format(exc)) from exc
        else:
            return process

    def cleanup(self):
        proc = self._process
        if proc is None:
            return

        log.info('Preparing to terminate ffmpeg process %s.', proc.pid)

        try:
            proc.kill()
        except Exception:
            log.exception("Ignoring error attempting to kill ffmpeg process %s", proc.pid)

        if proc.poll() is None:
            log.info('ffmpeg process %s has not terminated. Waiting to terminate...', proc.pid)
            proc.communicate()
            log.info('ffmpeg process %s should have terminated with a return code of %s.', proc.pid, proc.returncode)
        else:
            log.info('ffmpeg process %s successfully terminated with return code of %s.', proc.pid, proc.returncode)

        self._process = self._stdout = None

class FFmpegPCMAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).

    This launches a sub-process to a specific input file given.

    .. warning::

        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.

    Parameters
    ------------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to PCM bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.

    Raises
    --------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(self, source, *, executable='ffmpeg', pipe=False, stderr=None, before_options=None, options=None):
        args = []
        subprocess_kwargs = {'stdin': source if pipe else subprocess.DEVNULL, 'stderr': stderr}

        if isinstance(before_options, str):
            args.extend(shlex.split(before_options))

        args.append('-i')
        args.append('-' if pipe else source)
        args.extend(('-f', 's16le', '-ar', '48000', '-ac', '2', '-loglevel', 'warning'))

        if isinstance(options, str):
            args.extend(shlex.split(options))

        args.append('pipe:1')

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)

    def read(self):
        ret = self._stdout.read(OpusEncoder.FRAME_SIZE)
        if len(ret) != OpusEncoder.FRAME_SIZE:
            return b''
        return ret

    def is_opus(self):
        return False

from __future__ import print_function
import sys
import os
import tempfile
import time
import difflib
import webbrowser
import shutil
import pprint
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

try:
    import sublime, sublime_plugin
except ImportError:
    pass # probably just loading in Sublime 3

if (int(sublime.version()) <= 3000):
    import BGS_Perforce
    import mw
else:
    import PapyrusF4.BGS_Perforce as BGS_Perforce
    import PapyrusF4.mw as mw

# List of files that should be deleted in a version upgrade.
# Format is the version number, followed by a list of files to kill
UPGRADE_KILL_FILES = {
    # Example - 1.0: ["fileA.txt", "fileB.txt", "folder/"]
}
VERSION = 0.0

# This may only work on Windows 7 and up -- fine for our purposes
INI_LOCATION = os.path.expanduser("~/Documents/SublimePapyrusF4.ini")

UPDATE_TIMESTAMP_FILENAME = "updateTimeStamp.txt"

# Default values for a standardized Steam installation (for end-users and modders)
if (os.path.exists("C:\\Program Files (x86)")):
    END_USER_ROOT = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Fallout 4"
else:
    END_USER_ROOT = "C:\\Program Files\\Steam\\steamapps\\common\\Fallout 4"
END_USER_OUTPUT   = os.path.join(END_USER_ROOT, "Data\\Scripts")
END_USER_SCRIPTS  = os.path.join(END_USER_OUTPUT, "Source\\User")
END_USER_IMPORT   = "$(source);" + os.path.join(END_USER_OUTPUT, "Source\\Base")
END_USER_COMPILER = os.path.join(END_USER_ROOT, "Papyrus Compiler\\PapyrusCompiler.exe")
END_USER_ASSEMBLER = os.path.join(END_USER_ROOT, "Papyrus Compiler\\PapyrusAssembler.exe")
END_USER_FLAGS    = "Institute_Papyrus_Flags.flg"
END_USER_WIKI     = "http://www.creationkit.com"

DEFAULT_INI_TEXT = """; For the import setting:
; Separate folders with semicolons - but do not put whitespace in front of the semicolon or it will be treated as a comment
; Use $(source) to indicate location of scripts folder in the list

[Fallout4]
scripts={scripts}
import={importFolder}
compiler={compiler}
assembler={assembler}
output={output}
workspace=
flags={flags}
wiki={wiki}
""".format(scripts = END_USER_SCRIPTS, importFolder = END_USER_IMPORT, compiler = END_USER_COMPILER, assembler = END_USER_ASSEMBLER, output = END_USER_OUTPUT, flags = END_USER_FLAGS, wiki = END_USER_WIKI)

# Check to see if path is equal to - or a subdirectory of - target
def recursivePathCheck(path, target):
    path = os.path.normcase(path)
    target = os.path.normcase(target)
    if (path == target):
        return True

    while True:
        upPath = os.path.dirname(path)
        if (upPath == path):
            return False
        path = upPath
        if (path == target):
            return True


# Certain operations - like assembly/disassembly, actually have files in the output folder, instead of the
# script folder, so let them pick the configuration based off the output if they want
def getPrefs(currentDir, outputInsteadOfScripts = False):
    ret = {}

    if (not os.path.exists(INI_LOCATION)):
        ret["scripts"]   = END_USER_SCRIPTS
        ret["import"]    = END_USER_IMPORT
        ret["compiler"]  = END_USER_COMPILER
        ret["assembler"] = END_USER_ASSEMBLER
        ret["output"]    = END_USER_OUTPUT
        ret["workspace"] = "" # no P4 access for modders, but let's fill this in anyway
        ret["flags"]     = END_USER_FLAGS
        ret["wiki"]      = END_USER_WIKI
    else:
        parser = configparser.ConfigParser()
        parser.read(INI_LOCATION)
        for config in parser.sections():
            if config == "General":
                continue
            if outputInsteadOfScripts:
                path = parser.get(config, "output")
            else:
                path = parser.get(config, "scripts")
            if (recursivePathCheck(currentDir, path)):
                for k in parser.items(config):
                    ret[k[0]] = k[1]
                break

    if "import" in ret and "scripts" in ret:
        ret["import"] = ret["import"].replace("$(source)", ret["scripts"])
    if "scripts" in ret and not "import" in ret:
        ret["import"] = ret["scripts"]
    if "wiki" in ret and "wiki_api" not in ret:
        ret["wiki_api"] = ret["wiki"] + "api.php"
    if "wiki" in ret and "wiki_front" not in ret:
        ret["wiki_front"] = ret["wiki"] + "index.php"
    
    return ret


def processRecentUpgrade():
    if (VERSION in UPGRADE_KILL_FILES):
        print("Performing kill for version %1.1f" % (VERSION))
        for killed in UPGRADE_KILL_FILES[VERSION]:
            killPath = os.path.join(sublime.packages_path(), "PapyrusF4", killed)
            if os.path.exists(killPath):
                if killed[-1] == "/":
                    shutil.rmtree(killPath)
                else:
                    os.remove(killPath)


def autoUpdateCheck():
    if (not os.path.exists(INI_LOCATION)):
        print("PapyrusF4: No SublimePapyrusF4.ini file; skipping auto-update check.")
    else:
        print("PapyrusF4: Checking for internal auto-update...", end=' ')
        updateNeeded = False

        parser = configparser.ConfigParser()
        parser.read(INI_LOCATION)
        try:
            updatePath = parser.get("General", "update")
        except (configparser.NoSectionError, configparser.NoOptionError):
            updatePath = ""
        if updatePath != "":
            networkTimestamp = 0
            localTimestamp = 0
            
            networkTSFileName = os.path.join(updatePath, UPDATE_TIMESTAMP_FILENAME)
            if (os.path.exists(networkTSFileName)):
                with open(networkTSFileName, 'r') as timestampFileHandle:
                    timestamp = timestampFileHandle.read()
                networkTimestamp = float(timestamp)

            localTSFileName = os.path.join(sublime.packages_path(), "PapyrusF4", UPDATE_TIMESTAMP_FILENAME)
            if (os.path.exists(localTSFileName)):
                with open(localTSFileName, 'r') as timestampFileHandle:
                    timestamp = timestampFileHandle.read()
                localTimestamp = float(timestamp)

            if (networkTimestamp > localTimestamp):
                updateNeeded = True

        if (updateNeeded):
            print("updating from network.")
            walker = os.walk(updatePath)
            for path, dirs, files in walker:
                for f in files:
                    src = os.path.join(path, f)
                    rel = src[len(updatePath)+1:]
                    dst = os.path.join(sublime.packages_path(), "PapyrusF4", rel)
                    if not os.path.exists(os.path.dirname(dst)):
                        os.makedirs(os.path.dirname(dst))
                    shutil.copy2(src, dst)
        else:
            print("no update needed.")


def checkout(filename, prefs):
    output = BGS_Perforce.checkout(prefs["workspace"], filename)
    sublime.status_message(output)


# Creates a directory for our cache files, if necessary, in the OS's temporary folder
# We don't use the temporary directory creation tools Python supplies because we want the folder to stay the same
# between runs so we can continue to access it.
def ensureCacheDirectory():
    dirName = os.path.join(tempfile.gettempdir(), "SublimePapyrusF4")
    if not os.path.exists(dirName):
        os.makedirs(dirName)
    return dirName


# Get a filename for a file revision in perforce.
# We don't want to use the standard temporary file creation tools Python supplies because we want the name to
# reflect the file name in perforce and the revision number so the user knows what revision they are examining
def getRevisionFileName(truefilename, rev):
    basename = os.path.basename(truefilename)
    (rawFilename, extension) = os.path.splitext(basename)
    fname = ensureCacheDirectory()
    fname = os.path.join(fname, rawFilename) + "#{0}".format(rev) + extension
    return fname


def openDiffInTab(viewHandle, edit, oldTextName, newTextName, oldText, newText):
    diffs = difflib.unified_diff(oldText.splitlines(), newText.splitlines(), oldTextName, newTextName)
    diffText = u"\n".join(line for line in diffs)

    if diffText == "":
        sublime.status_message("No changes between revisions.")
    else:
        scratch = viewHandle.window().new_file()
        scratch.set_scratch(True)
        scratch.set_name("{old} -> {new}".format(old = oldTextName, new = newTextName))
        scratch.set_syntax_file("Packages/Diff/Diff.tmLanguage")

        if (int(sublime.version()) >= 3000):
            scratch.run_command("append", {"characters": diffText})
        else:
            scratch.insert(edit, 0, diffText)


class PapyrusF4ViewOldRevisionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.fileName = self.view.file_name()
        prefs = getPrefs(os.path.dirname(self.fileName))
        revs = BGS_Perforce.getRevisionListFor(prefs["workspace"], self.fileName)
        self.revLength = len(revs)
        self.view.window().show_quick_panel(revs, self.onSelect)


    def onSelect(self, index):
        if (index == -1):
            return
        rev = self.revLength - index
        prefs = getPrefs(os.path.dirname(self.fileName))
        revText = BGS_Perforce.getRevisionText(prefs["workspace"], self.fileName, rev)
        
        tempFileName = getRevisionFileName(self.fileName, rev)
        with open(tempFileName, "w") as tempFileHandle:
            tempFileHandle.write(revText)

        self.view.window().open_file(tempFileName)


class PapyrusF4DiffOldRevisionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.edit = edit
        self.fileName = self.view.file_name()
        prefs = getPrefs(os.path.dirname(self.fileName))
        revs = BGS_Perforce.getRevisionListFor(prefs["workspace"], self.fileName)
        self.revLength = len(revs)
        self.view.window().show_quick_panel(revs, self.onSelect)


    def onSelect(self, index):
        if (index == -1):
            return
        rev = self.revLength - index
        prefs = getPrefs(os.path.dirname(self.fileName))
        revText = BGS_Perforce.getRevisionText(prefs["workspace"], self.fileName, rev)
        currText = self.view.substr(sublime.Region(0, self.view.size()))

        openDiffInTab(self.view, self.edit, self.fileName, "Perforce revision #{0}".format(rev), revText, currText)


class PapyrusF4DiffAgainstPerforceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.fileName = self.view.file_name()
        prefs = getPrefs(os.path.dirname(self.fileName))
        revs = BGS_Perforce.getRevisionListFor(prefs["workspace"], self.fileName)
        revText = BGS_Perforce.getRevisionText(prefs["workspace"], self.fileName)
        currText = self.view.substr(sublime.Region(0, self.view.size()))

        openDiffInTab(self.view, edit, self.fileName, "Perforce head", revText, currText)


class PapyrusF4CheckOutFromP4Command(sublime_plugin.TextCommand):
    def run(self, edit):
        checkout(self.view.file_name())


class PreEmptiveCheckOutPlugin(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        prefs = getPrefs(os.path.dirname(view.file_name()))
        if (len(prefs) > 0):
            if (not os.access(view.file_name(), os.W_OK)):
                checkout(view.file_name(), prefs)


class PapyrusF4CreateDefaultSettingsFileCommand(sublime_plugin.WindowCommand):
    def run(self, **args):
        if os.path.exists(INI_LOCATION):
            sublime.status_message("ERROR: INI file already exists at {0}".format(INI_LOCATION))
        else:
            with open(INI_LOCATION, "w") as outHandle:
                outHandle.write(DEFAULT_INI_TEXT)
            self.window.open_file(INI_LOCATION)

def compilePapyrus(args, window, optimize, release, final):
    config = getPrefs(os.path.dirname(args["cmd"]))
    if config:
        scriptPath = args["cmd"][len(config["scripts"])+1:]

        args["cmd"] = [config["compiler"], scriptPath]
        args["cmd"].append("-f={0}".format(config["flags"]))
        args["cmd"].append("-i={0}".format(config["import"]))
        args["cmd"].append("-o={0}".format(config["output"]))
        if optimize:
            args["cmd"].append("-op")
        if release:
            args["cmd"].append("-r")
        if final:
            args["cmd"].append("-final")

        args["working_dir"] = os.path.dirname(config["compiler"])

        window.run_command("exec", args)
    else:
        sublime.status_message("No configuration for {0}".format(os.path.dirname(args["cmd"])))

class CompilePapyrusF4Command(sublime_plugin.WindowCommand):
    def run(self, **args):
        # "Debug" build - no optimization, no stripping
        compilePapyrus(args, self.window, optimize=False, release=False, final=False)

class CompilePapyrusF4ReleaseFinalCommand(sublime_plugin.WindowCommand):
    def run(self, **args):
        # "Release final" build - optimization and full stripping
        compilePapyrus(args, self.window, optimize=True, release=True, final=True)

class CompilePapyrusF4ReleaseCommand(sublime_plugin.WindowCommand):
    def run(self, **args):
        # "Release beta" build - optimization and debug stripping
        compilePapyrus(args, self.window, optimize=True, release=True, final=False)

class DisassemblePapyrusF4Command(sublime_plugin.WindowCommand):
    def run(self, **args):
        config = getPrefs(os.path.dirname(args["cmd"]), outputInsteadOfScripts = True)
        if (config):
            scriptPath = args["cmd"]

            scriptDir = os.path.dirname(scriptPath)
            scriptName = os.path.splitext(os.path.basename(scriptPath))[0]
            args["cmd"] = [config["assembler"], scriptName]
            args["cmd"].append("-D")

            args["working_dir"] = scriptDir

            self.window.run_command("exec", args)

            disassembly = os.path.join(scriptDir, scriptName + ".disassemble.pas")
            disassemblyFinal = os.path.join(scriptDir, scriptName + ".pas")

            # the above exec can take some time, and Sublime doesn't want for it to finish, so try to wait a second or so
            # for it to finish, by keeping an eye on whether the disassembly file is available
            loopCount = 0
            while (not os.path.exists(disassembly)) and (loopCount < 10):
                time.sleep(0.1)
                loopCount += 1
            if os.path.exists(disassembly):
                os.rename(disassembly, disassemblyFinal)
                if (os.path.exists(disassemblyFinal)):
                    self.window.open_file(disassemblyFinal)
        else:
            sublime.status_message("No configuration for {0}".format(os.path.dirname(args["cmd"])))


class AssemblePapyrusF4Command(sublime_plugin.WindowCommand):
    def run(self, **args):
        config = getPrefs(os.path.dirname(args["cmd"]), outputInsteadOfScripts = True)
        if (config):
            scriptPath = args["cmd"]

            scriptDir = os.path.dirname(scriptPath)
            scriptName = os.path.splitext(os.path.basename(scriptPath))[0]
            args["cmd"] = [config["assembler"], scriptName]

            args["working_dir"] = scriptDir

            self.window.run_command("exec", args)


class PapyrusF4WikiDocumentationCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.fileName = self.view.file_name()
        self.prefs = getPrefs(os.path.dirname(self.fileName))
        
        refresh = False
        # does cache file exist?
        fname = ensureCacheDirectory()
        fname = os.path.join(fname, "WikiPagesCache.txt")
        if not os.path.exists(fname):
            refresh = True
        else:
            touched = os.path.getmtime(fname)
            three_days = time.time() - 60*60*24*3 # three days ago in seconds
            if touched < three_days:
                refresh = True

        if (refresh):
            if (int(sublime.version()) >= 3000):
                outText = "\n".join(list(self.getPapyrusPages())).strip()
            else:
                outText = "\n".join(list(self.getPapyrusPages())).encode("utf-8").strip()
            with open(fname, "w") as fileHandle:
                fileHandle.write(str(outText))

        with open(fname, "r") as f:
            self.papyrusPages = f.readlines()

        self.processingSelections = self.view.sel()

        self.pagesToOpen = []
        self.processTopSelection()

    def getPapyrusPages(self):
        ck_wiki = mw.Wiki(self.prefs["wiki_api"])
        params = {
            'action':'query',
            'list':'categorymembers',
            'cmtitle':'Category:Papyrus',
            'cmlimit':500,
            'cmprop':'title'
        }
        while True:
            data = ck_wiki.request(params)
            for item in data['query']['categorymembers']:
                yield item['title']
            try:
                params['cmcontinue'] = data['query-continue']['categorymembers']['cmcontinue']
            except:
                break

    def processTopSelection(self):
        if len(self.processingSelections) <= 0:
            for page in self.pagesToOpen:
                webbrowser.open(page)
            return

        selection = self.processingSelections[0]
        del self.processingSelections[0]
        text = self.view.substr(self.view.word(selection))
        # print "Processing %i; %s:" % (len(self.processingSelections), text),
        self.candidates = []
        for page in self.papyrusPages:
            try:
                if page.lower().startswith(text.lower() + " "):
                    self.candidates.append(page)
            except UnicodeDecodeError:
                continue

        # print self.candidates
        if   (len(self.candidates) == 0):
            sublime.status_message("No documentation found for %s" % (text))
            self.processTopSelection()
        elif (len(self.candidates) == 1):
            self.pagesToOpen.append(self.prefs["wiki_front"] + "/" + self.candidates[0])
            self.processTopSelection()
        else:
            # was going to make this super clever, but forget that; just
            #  let the user choose
            self.view.window().show_quick_panel(self.candidates, self.onSelect)


    def onSelect(self, index):
        if (index != -1):
            self.pagesToOpen.append(self.prefs["wiki_front"] + "/" + self.candidates[index])
        self.processTopSelection()
        


####################################
# BGS Internal Auto-update check   #
####################################
def Init():
    global VERSION
    try:
        with open(os.path.join(sublime.packages_path(), "PapyrusF4", "VERSION"), "r") as version_file:
            VERSION = float(version_file.read())
    except:
        pass # VERSION remains 0.0

    autoUpdateCheck()
    processRecentUpgrade()


if (int(sublime.version()) >= 3000):
    # we're loading in Sublime 3; have to wait
    import sublime, sublime_plugin
    def plugin_loaded():
        Init()
else:
    # Sublime 2; we can import and call directly
    Init()

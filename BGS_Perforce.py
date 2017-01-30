import sys, os
import subprocess
import pprint
import re

class BGS_P4Error(Exception):
    pass

def _p4run(cmd, workspace):
    cmd = ["p4", "-c", workspace] + cmd
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (i, o, e) = (p.stdin, p.stdout, p.stderr)
    output = o.read().decode("utf-8").strip()
    error = e.read().decode("utf-8").strip()
    i.close()
    e.close()
    retval = o.close()
    if retval:
        raise BGS_P4Error("Error running '%s': error='%s' retval='%s'" % (cmd, error, retval))
    return output, error, retval

def checkout(workspace, filename):
    o, e, r = _p4run(["edit", filename], workspace)
    return o

def getRevisionText(workspace, filename, revision=None):
    if revision != None:
        fileRange = "%s#%s" % (filename, revision)
    else:
        fileRange = filename
    o, e, r = _p4run(["print", "-q", fileRange], workspace)
    return o.replace("\r\n", "\n")

def getRevisionListFor(workspace, filename):
    o, e, r = _p4run(["filelog", "-l", filename], workspace)
    output_fixed = o.replace("\r", "").replace("\n\n\t", "")

    hits = []
    revRe = re.compile("^... #(?P<rev>\d+) change (?P<change>\d+) "\
        "(?P<action>\w+) on (?P<date>[\d/]+) by "\
        "(?P<user>[^\s@]+)@(?P<client>[^\s@]+) "\
        "\((?P<type>[\w+]+)\)(?P<description>.*?)$")
    for line in output_fixed.splitlines(1):
        if not line.strip():
            continue
        elif line.startswith('//'):
            hit = {'depotFile': line.strip(), 'revs': []}
            hits.append(hit)
        elif line.startswith('... ... '):
            hits[-1]['revs'][-1]['notes'].append(line[8:].strip())
        elif line.startswith('... '):
            match = revRe.match(line)
            if match:
                d = match.groupdict('')
                d['change'] = int(d['change'])
                d['rev'] = int(d['rev'])
                hits[-1]['revs'].append(d)
                hits[-1]['revs'][-1]['notes'] = []
            else:
                raise BGS_P4Error("Internal parsing error: '%s'" % line)
        elif longOutput and line.startswith('\t'):
            # Append this line (minus leading tab) to last hit's
            # last rev's description.
            hits[-1]['revs'][-1]['description'] += line[1:]
        else:
            raise BGS_P4Error("Unexpected 'p4 filelog' output: '%s'"\
                             % line)
    revList = []
    raw_revisions = hits[0]["revs"]
    width = len(str(len(raw_revisions)))
    for rev in raw_revisions:
        revString = "[%s]: %s, %s" % (str(rev["rev"]).zfill(width), rev["user"], rev["date"])
        descString = rev["description"]
        revTuple = [revString, descString]
        revList.append(revTuple)
    return revList

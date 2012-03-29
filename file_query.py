#!/usr/bin/python3
"""
This program is intended to be pointed at a directory that contains TXT files. 
The program will then create a CSV (sep=, quote=") or DAT (sep=| quote=^) or HTML file 
that includes metadata about the files and some columns populated with file text.
"""

# this is a git test!
# this should appear in diff

import optparse, os, sys, re
import glob, csv, subprocess

def process_options():
    parser = optparse.OptionParser(
    usage = ("%prog INDIR OUTDIR [options] " 
    "\nThis program writes DAT, CSV, or HTML metadata files to OUTDIR from readable files in INDIR."))

    parser.add_option("--all", dest="all",
            action="store_true",
            help=("run on all files in INDIR (not just .txt) [default: off]"))
    parser.add_option("-r", "--recursive", dest="recursive",
            action="store_true",
            help=("recurse into subdirectories (but not .hidden) [default: off]"))
    parser.add_option("--text-size", dest="text_size", type='int',
            help=("number of characters read into text field [default: %default]"))
    parser.add_option("--memo-size", dest="memo_size", type='int',
            help=("number of characters read into text field [default: %default]"))
    parser.add_option("--list-size", dest="list_size", type='int',
            help=("number of characters read into text field [default: %default]"))    
    parser.add_option("-f", "--format", action="store", type="string", dest="file_format",
            help=("Format of output file may be DAT (pipe separated), CSV, or HTML [default: %default]"))    

    parser.set_defaults(text_size=20,list_size=20,memo_size=100,file_format="DAT")
    opts, args = parser.parse_args()

    if len(args) < 2: 
        parser.error("both IN and OUT directories must be specified!\n")
    elif (opts.text_size + opts.list_size + opts.memo_size > 2000):
        parser.error("you are reading too much text! please ask for less!\n")
    return opts, args


def get_filenames(recurse, all_files):
    """
    Function to get a list of files per user request. 
    Note that we CWD prior to function call, so walking from .
    If recurse, walk. Otherwise, use os.listdir.
    """ 

    mylist = []
    if (recurse):
        # I've totally given up on os.walk, so do the directory walking manually
        directories = [os.getcwd()]
        while len(directories) > 0: 
            directory = directories.pop()
            for name in os.listdir(directory): 
                fullpath = os.path.join(directory,name)
                if (os.path.isfile(fullpath)):
                    # I want to append only .txt files unless --all is requested
                    if all_files:
                        mylist.append(fullpath)
                    else:
                        if name.endswith(".txt"):
                            mylist.append(fullpath)
                        else: 
                            #skip if not text and not --all
                            continue
                else: # this is a directory
                    if (os.path.basename(fullpath)[0] != '.'): 
                        # skip hidden directories
                        directories.append(fullpath)
    else:
       # not recursing subdirs, so use glob to get filelist in the current directory
       # note that .TXT and .txt are both globbed (WINDOZE only! Need to fix this!)
        if all_files:
            myglob = '*'
        else:
            myglob = '*.txt'
        for files in glob.glob(myglob):
            if os.path.isfile(files):
                mylist.append(os.path.realpath(files))
    return mylist


def get_metadata(filelist): 
    '''
    This function takes a list of filenames and returns a dict including metadata associated with each file.
    The dictionary key is the file name plus path from get_filenames(). Use subprocess to run "file" and "wc".
    '''
    mydict = {}

    # here is a helper function from stack overflow. I added the regex stuff.
    def count_words(fname):
        p = subprocess.Popen(['wc', fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, err = p.communicate()
        if p.returncode != 0:
            raise IOError(err)
        #regex to capture three numerics from `wc`: lines, words, chars
        q = result.decode("utf-8")
        wcpat = re.compile(r'[0-9]+')
        xx = wcpat.findall(q)
        wc_str = "lines={} words={} chars={}".format(xx[0],xx[1],xx[2])
        return wc_str

    def unix_file(fname):
        # this function runs unix "file" command on all files encountered
        p = subprocess.Popen(['file', fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, err = p.communicate()
        if p.returncode != 0:
            raise IOError(err)
        y = result.decode("utf-8")
        # regex to remove leading filename from `file`. Stop at ':'
        # should compile outside of this sub, no?
        mypat = re.compile(r'^[^:]+')
        z = re.sub(mypat,'File',y)
        return z

    for fullname in filelist: 
        # get some metadata. In a unix env, I will want to call `file` and `wc` and add that data to dict
        (filename,extension) = os.path.splitext(fullname)
        shortname = os.path.basename(filename)
        fsize = "{} bytes".format(str(os.stat(fullname).st_size))
        # run `file` on all files in list
        unixfile = unix_file(fullname)
        # wordcount is for text files only
        if fullname.endswith("txt") :
            wordcount = count_words(fullname)
        else : 
            wordcount = "not applicable"

        # create our dict with key fullname
        mydict[fullname]={'filename':shortname}
        # append the other data to the dict
        mydict[fullname].update({'filename':shortname,'extension':extension,'fsize':fsize,'wc_cmd':wordcount,'file_cmd':unixfile})
    return mydict


def get_filetext(mydict,textchar,listchar,memochar):
    # let's put an assertion in for specified text too large 
    assert (textchar + listchar + memochar < 20000), "too much text requested!"

    # helper function to add empty values to dict if error occurs
    # will ensure that all rows have same number of columns
    def writeblanks(fullname): 
        myblank = {'TEXT':'NA','LIST':'NA','MEMO':'NA','MEMOASC':'NA'}
        mydict[fullname].update(myblank)

    # open filename from dictionary key
    for fullname in mydict.keys(): 
        if mydict[fullname]['extension'].lower() == '.txt':
            # attempt read from text files
            myfile = None
            try:
                myfile = open(fullname,encoding='utf-8',mode='r')
            except EnvironmentError as fileerr:
                writeblanks(fullname)
                mydict[fullname]['ERROR'] = 'Could not open file for reading'                    
                #continue    
            else:
                # populate the dict with file text
                try: 
                    achar = myfile.read(int(textchar))
                    bchar = myfile.read(int(listchar))
                    cchar = myfile.read(int(memochar))
                except (UnicodeDecodeError,UnicodeEncodeError) as texterr:
                    # think about closing and reopening text file as binary here?
                    writeblanks(fullname)
                    mydict[fullname]['ERROR'] = 'This file was not (all) unicode!'
                except EOFError as eoferr:
                    writeblanks(fullname)
                    mydict[fullname]['ERROR'] = 'Ran into the the EOF in this file!'
                else:
                    # read succeeded, replace string newlines with "<NL>"
                    aachar = achar.replace('\n','<NL>')
                    bbchar = bchar.replace('\n','<NL>')
                    ccchar = cchar.replace('\n','<NL>')
                    # now append the text to the dict, Jim Dean's idea
                    mytext = {'TEXT':aachar,'LIST':bbchar,'MEMO':ccchar,'MEMOASC':ascii(ccchar),'ERROR':'none'}
                    mydict[fullname].update(mytext)
            finally:
                if myfile is not None:
                    myfile.close()
        else:
            # this was not a text file
            writeblanks(fullname)
            mydict[fullname]['ERROR'] = 'Not Text'        
    return mydict


def write_file(fhandle,mydict,FORMAT):
    '''
    This function writes out mydict data in the format specified by user (DAT, CSV or HTML)
    Note that key to mydict is full filename.
    ''' 
    if FORMAT == 'html':
        print("writing an HTML file!")
    elif FORMAT == 'csv': 
        print("writing a CSV file!")

        writer = csv.writer(fhandle, quoting=csv.QUOTE_ALL)
        # write the CSV header
        writer.writerow( ('fullname','file name','extension','file size','word count','file description','text field','list field','memo field','memo field ASC','errors') )
        # do I want to write sorted keys here?
        for myfile in mydict.keys():

            #writer.writerow(file_info[key] for key in ['filename', 'extension', 'fsize', 'TEXT', 'ASCTEXT', 'LIST', 'MEMO', 'ERROR']])

            writer.writerow( (myfile,mydict[myfile]['filename'],mydict[myfile]['extension'],mydict[myfile]['fsize'],mydict[myfile]['wc_cmd'],mydict[myfile]['file_cmd'],mydict[myfile]['TEXT'],mydict[myfile]['LIST'],mydict[myfile]['MEMO'],mydict[myfile]['MEMOASC'],mydict[myfile]['ERROR']) )
    else: 
        print("writing a DAT file!")
    return 1


def main():
    # get the options passed in or parsererror
    opts, paths = process_options()
    # need to make these arguments into globals to pass them around, apparently
    TEXT_FIELD_CHARS = opts.text_size
    LIST_FIELD_CHARS = opts.list_size
    MEMO_FIELD_CHARS = opts.memo_size
    RECURSE = opts.recursive
    MYALL = opts.all

    # create filename based on format specified
    if (opts.file_format.lower() == 'csv' or opts.file_format.lower() == 'html'):
        FILE_FORMAT = opts.file_format.lower()
    else:
        FILE_FORMAT = 'dat' 
    # I should join here...
    FILE_NAME = 'datafile' + '.' + FILE_FORMAT
    #output1 = subprocess.check_output('file *',shell=True,)
    
    # test INDIR directory exists and is accessible
    INDIR,OUTDIR = (paths[0],paths[1])
    print("INDIR = {}".format(INDIR))
    try:
        os.chdir(INDIR)
    except OSError as inputerr:
        print("Could not read directory {}! Try again!\n{}".format(os.path.realpath(INDIR),inputerr))
        return

    # test writing to OUTDIR directory is allowed
    WFILE = None
    # having some trouble getting the outfile to work. Writing to INDIR location currently... 
    outfile = os.path.join(os.path.realpath(OUTDIR),FILE_NAME)
    print("OUTDIR = {}".format(outfile))
    try:
        WFILE = open(outfile, mode='wt',encoding='utf-8')
    except EnvironmentError as openerr:
        print("Could not open {} for writing!".format(openerr))
    else:
        # ready to read data and write output file
        print("Writing data file = {} to directory {}\n".format(FILE_NAME,os.path.realpath(paths[1])))
        # get filelist per user options 
        myfiles = get_filenames(RECURSE, MYALL)

        # get metadata for the files in list
        mydict = get_metadata(myfiles)

        # get filedata from TXT files and add to mydict
        mydict = get_filetext(mydict,TEXT_FIELD_CHARS,LIST_FIELD_CHARS,MEMO_FIELD_CHARS)

        # write out mydict data in user specified format
        write_file(WFILE, mydict, FILE_FORMAT)

        print("dict size is {} ".format(len(mydict)))
        #for file in myfiles:
        for file in mydict.keys():
             print("file is {}!".format(file)) 

    finally:
        if WFILE is not None:
            WFILE.close()

main()

# the end

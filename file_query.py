#!/usr/bin/python3
"""
This program is intended to be pointed at a directory that contains TXT files. 
The program will then create a CSV (sep=, quote=") or HTML file that includes 
metadata about the files and a column populated with file text (where applicable).
"""

import optparse, os, sys, re, time
import glob, csv, subprocess

def main():
    # Seems that __file__ is totally getting lost after a chdir (windows and linux). 
    # So just save the path when the script is started, and change back after reading files.
    ORIG = os.path.dirname(os.path.realpath(sys.argv[0]))
    # get the options passed in or parsererror
    opts, paths = process_options()
    # need to make these arguments into globals to pass them around, apparently
    EXTRACTED_TEXT = opts.text_size
    RECURSE = opts.recursive
    MYALL = opts.all

    # allow HTML file, else default to CSV writing, also put a timestamp into filename
    if (opts.file_format.lower() == '.html'):
        FILE_FORMAT = opts.file_format.lower()
    else:
        FILE_FORMAT = '.csv' 
    FILE_NAME = 'datafile_' + str(int(time.time())) + FILE_FORMAT
    
    # test INDIR directory exists and is accessible
    INDIR = (paths[0])
    try:
        os.chdir(INDIR)
    except OSError as inputerr:
        print("Could not read directory {}! Try again!\n{}".format(os.path.realpath(INDIR),inputerr))
        return 

    # get filelist per user options, bail if nothing returned
    myfiles = get_filenames(RECURSE, MYALL)
    if len(myfiles) < 1:
        print("No files in directory {}! Use --all?\n".format(os.path.realpath(INDIR)))
        return 

    # get metadata for the files in list
    mydict = get_metadata(myfiles)

    # append extracted text to mydict
    mydict = get_filetext(mydict,EXTRACTED_TEXT)

    WFILE = None
    # Put the datafile in same dir as this script. Simpler that way.
    os.chdir(ORIG)
    #print("moved here {} and dirname = {}\n".format(os.getcwd(),os.path.dirname(os.path.realpath(sys.argv[0]))))
 
    try:
        WFILE = open(FILE_NAME, mode='wt',encoding='utf-8')
    except EnvironmentError as openerr:
        print("Could not open {} for writing!\n".format(FILE_NAME))
    else:
        # write out mydict data in user specified format
        write_csv(WFILE, mydict, FILE_FORMAT)
    finally:
        if WFILE is not None:
            WFILE.close()

    # debug stuff
    print("dict size is {} ".format(len(mydict)))
    for file in mydict.keys():
         print("file is {}!".format(file)) 

def process_options():
    parser = optparse.OptionParser(
    usage = ("%prog INDIR [options] " 
    "\nThis program writes CSV or HTML files with metadata from readable files in INDIR."
    "\nUse --help or -h to see options."))

    parser.add_option("--all", dest="all",
            action="store_true",
            help=("run on all files in INDIR (not just .txt) [default: off]"))
    parser.add_option("-r", "--recursive", dest="recursive",
            action="store_true",
            help=("recurse into subdirectories (but not .hidden) [default: off]"))
    parser.add_option("--text-size", dest="text_size", type='int',
            help=("number of characters read into text field [default: %default]"))
    parser.add_option("-f", "--format", action="store", type="string", dest="file_format",
            help=("Format of output file may be CSV or HTML [default: %default]"))    
    parser.set_defaults(text_size=200,file_format="CSV")
    opts, args = parser.parse_args()

    # a parser error quits after message
    if len(args) < 1: 
        parser.error("IN directory must be specified!\n")
    elif (opts.text_size > 2000):
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

    # wc function. Some of this from stack overflow. I added the regex stuff.
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

    mydict = {}
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



def get_filetext(mydict,textchar):
    # let's put an assertion in for specified text too large 
    assert (textchar < 20000), "too much text requested!"

    # helper function to add empty values to dict if error occurs
    # will ensure that all rows have same number of columns
    def writeblanks(fullname): 
        myblank = {'TEXT':'NA','TEXTASC':'NA'}
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
                except (UnicodeDecodeError,UnicodeEncodeError) as texterr:
                    # think about closing and reopening text file as binary here?
                    writeblanks(fullname)
                    mydict[fullname]['ERROR'] = 'This file was not (all) unicode!'
                except EOFError as eoferr:
                    writeblanks(fullname)
                    mydict[fullname]['ERROR'] = 'Ran into End Of File!'
                else:
                    # read succeeded, replace string newlines with "<NL>"
                    aachar = achar.replace('\n','<NL>')
                    # now append the text to the dict, Jim Dean's idea
                    mytext = {'TEXT':aachar,'TEXTASC':ascii(aachar),'ERROR':'none'}
                    mydict[fullname].update(mytext)
            finally:
                if myfile is not None:
                    myfile.close()
        else:
            # this was not a text file
            writeblanks(fullname)
            mydict[fullname]['ERROR'] = 'Not Text'        
    return mydict


def write_csv(fhandle,mydict,FORMAT):
    '''
    This function writes out mydict data in the format specified by user (CSV or HTML)
    Note that key to mydict is filename + path.
    ''' 
    if FORMAT == '.html':
        print("writing an HTML file!")
    else : 
        print("writing a CSV file!")
        writer = csv.writer(fhandle, quoting=csv.QUOTE_ALL)
        # write the CSV header
        writer.writerow( ('fullname','file name','extension','file size','word count','file description','text field','text field ASC','errors') )
        # do I want to write sorted keys here?
        for myfile in mydict.keys():
            writer.writerow( (myfile,mydict[myfile]['filename'],mydict[myfile]['extension'],mydict[myfile]['fsize'],mydict[myfile]['wc_cmd'],mydict[myfile]['file_cmd'],mydict[myfile]['TEXT'],mydict[myfile]['TEXTASC'],mydict[myfile]['ERROR']) )
    return 1

main()
# the end

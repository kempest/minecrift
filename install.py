import os, os.path, sys
import zipfile, urllib2
import platform
import shutil, tempfile, json
import errno
import platform
import shutil
import time
from shutil import move
from tempfile import mkstemp
from os import remove, close
from minecriftversion import mc_version, of_file_name, of_json_name, minecrift_version_num, minecrift_build, of_file_extension, of_file_md5, mcp_version, mc_file_md5
from hashlib import md5  # pylint: disable-msg=E0611
from optparse import OptionParser
from applychanges import applychanges, apply_patch


base_dir = os.path.dirname(os.path.abspath(__file__))

preferredarch = ''
nomerge = False
nopatch = False
nocompilefixpatch = False
clean = False
force = False
dependenciesOnly = False

try:
    WindowsError
except NameError:
    WindowsError = OSError

def osArch():
    if platform.machine().endswith('64'):
        return '64'
    else:
        return '32'

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

#Helpers taken from forge mod loader, https://github.com/MinecraftForge/FML/blob/master/install/fml.py
def get_md5(file):
    if not os.path.isfile(file):
        return ""
    with open(file, 'rb') as fh:
        return md5(fh.read()).hexdigest()

def download_file(url, target, md5=None):
    name = os.path.basename(target)
    download = True
    if not is_non_zero_file(target):
        if os.path.isfile(target):
            os.remove(target)
        download = True
    elif not md5 == None and not md5 == "":
        if not get_md5(target) == md5:
            print 'File Exists but bad MD5!: %s [MD5:%s]' % ( os.path.basename(target), get_md5(target) )
            os.remove(target)
            download = True
        else:
            print 'File Exists: %s [MD5:%s]' % ( os.path.basename(target), get_md5(target) )
            download = False
    else:
        print 'File Exists: %s' % os.path.basename(target)
        download = False 
        
    if download is True:
        print 'Downloading: %s' % os.path.basename(target)
        try:
            with open(target,"wb") as tf:
                res = urllib2.urlopen(urllib2.Request( url, headers = {"User-Agent":"Mozilla/5.0"}))
                tf.write( res.read() )
            if not md5 == None and not md5 == "":
                if not get_md5(target) == md5:
                    print 'Download of %s failed md5 check, deleting' % name
                    os.remove(target)
                    return False
        except Exception as e:
            print e
            print 'Download of %s failed, download it manually from \'%s\' to \'%s\'' % (target, url, target)
            if os.path.isfile(target):
                os.remove(target)
            return False

    return True

def download_native(url, folder, name):
    if not os.path.exists(folder):
        os.makedirs(folder)

    target = os.path.join(folder, name)
    if not download_file(url, target):
        return False

    return True

def is_non_zero_file(fpath):  
    return True if os.path.isfile(fpath) and os.path.getsize(fpath) > 0 else False

def installAndPatchMcp( mcp_dir ):

    mcp_exists = True
    if not os.path.exists(mcp_dir+"/runtime/commands.py"):
        mcp_exists = False
        try:
            mcp_zip_file = os.path.join( base_dir,mcp_version+".zip" )
            if os.path.exists( mcp_zip_file ):
                os.mkdir( mcp_dir )
                mcp_zip = zipfile.ZipFile( mcp_zip_file )
                mcp_zip.extractall( mcp_dir )
                import stat
                astyle = os.path.join(mcp_dir,"runtime","bin","astyle-osx")
                st = os.stat( astyle )
                os.chmod(astyle, st.st_mode | stat.S_IEXEC)
                mcp_exists = True
        except:
            pass

    if mcp_exists == False:
        print "No %s directory or zip file found. Please copy the %s.zip file into %s and re-run the command." % (mcp_dir, mcp_dir, base_dir)
        exit(1)
    
    # Patch mcp.cfg for additional mem
    print("Patching mcp.cfg. Ignore \"FAILED\" hunks")
    apply_patch( mcp_dir, os.path.join("mcppatches", "mcp.cfg.patch"), os.path.join(mcp_dir,"conf"))
    
    # Patch mcp.cfg with minecraft jar md5
    mcp_cfg_file = os.path.join(mcp_dir,"conf","mcp.cfg")
    replacelineinfile( mcp_cfg_file, "MD5Client  =", "MD5Client  = %s\n" % mc_file_md5, True );   # Multiple 'MD5Client' entries - hack to get first one currently
    #replacelineinfile( mcp_cfg_file, "MD5Server  =", "MD5Server  = %s\n" % mc_server_file_md5, True );

    # patch joined.srg if necessary
    mcp_joined_srg = os.path.join(mcp_dir,"conf","joined.srg")
    patch_joined_srg = os.path.join(base_dir,"mcppatches","joined.srg")
    if os.path.exists(patch_joined_srg):
        print 'Updating joined.srg: copying %s to %s' % (patch_joined_srg, mcp_joined_srg)
        shutil.copy(patch_joined_srg,mcp_joined_srg)

    # Patch fffix.py
    fffix_patch_path = os.path.join(base_dir, "mcppatches", "fffix.py.patch")
    if os.path.exists(fffix_patch_path):
        print("Patching fffix.py. Ignore \"FAILED\" hunks")
        apply_patch( mcp_dir, os.path.join("mcppatches", "fffix.py.patch"), os.path.join(mcp_dir,"runtime","pylibs"))

    # Patch Start.java with minecraft version
    start_java_file = os.path.join(base_dir,"mcppatches","Start.java")
    target_start_java_file = os.path.join(mcp_dir,"conf","patches","Start.java")
    print 'Updating Start.java: copying %s to %s' % (start_java_file, target_start_java_file)
    shutil.copy(start_java_file,target_start_java_file)
    replacelineinfile( target_start_java_file, "args = concat(new String[] {\"--version\", \"mcp\"", "        args = concat(new String[] {\"--version\", \"mcp\", \"--accessToken\", \"0\", \"--assetsDir\", \"assets\", \"--assetIndex\", \"%s\", \"--userProperties\", \"{}\"}, args);\n" % mc_version );
    
    # Setup the appropriate mcp file versions
    mcp_version_cfg = os.path.join(mcp_dir,"conf","version.cfg")
    replacelineinfile( mcp_version_cfg, "ClientVersion =", "ClientVersion = %s\n" % mc_version );
    replacelineinfile( mcp_version_cfg, "ServerVersion =", "ServerVersion = %s\n" % mc_version );

    # Patch in mcp mappings (if present)
    params_csv_source = os.path.join(base_dir,"mcppatches","mappings","params.csv")
    params_csv_dest = os.path.join(mcp_dir,"conf","params.csv")
    if os.path.exists(params_csv_source):
        shutil.copy(params_csv_source,params_csv_dest)

    methods_csv_source = os.path.join(base_dir,"mcppatches","mappings","methods.csv")
    methods_csv_dest = os.path.join(mcp_dir,"conf","methods.csv")
    if os.path.exists(methods_csv_source):
        shutil.copy(methods_csv_source,methods_csv_dest)

    fields_csv_source = os.path.join(base_dir,"mcppatches","mappings","fields.csv")
    fields_csv_dest = os.path.join(mcp_dir,"conf","fields.csv")
    if os.path.exists(fields_csv_source):
        shutil.copy(fields_csv_source,fields_csv_dest)


def download_deps( mcp_dir, download_mc, forgedep=False ):

    jars = os.path.join(mcp_dir,"jars")

    versions =  os.path.join(jars,"versions",mc_version)
    mkdir_p( versions )

    if sys.platform == 'darwin':
        native = "osx"
    elif sys.platform == "linux":
        native = "linux"
    elif sys.platform == "linux2":
        native = "linux"
    else:
        native = "windows"

    if not forgedep:
        flat_lib_dir = os.path.join(base_dir,"lib",mc_version)
        flat_native_dir = os.path.join(base_dir,"lib",mc_version,"natives",native)
    else:
        flat_lib_dir = os.path.join(base_dir,"lib",mc_version+"-forge")
        flat_native_dir = os.path.join(base_dir,"lib",mc_version+"-forge","natives",native)

    mkdir_p( flat_lib_dir )
    mkdir_p( flat_native_dir )
     
    # Get minecrift json file
    json_file = os.path.join(versions,mc_version+".json")
    if forgedep is False:
        source_json_file = os.path.join("installer",mc_version+".json")
        print 'Updating json: copying %s to %s' % (source_json_file, json_file)
        shutil.copy(source_json_file,json_file)
    else:
        source_json_file = os.path.join("installer",mc_version+"-forge.json")
    
    # Use optifine json name for destination dir and jar names
    optifine_dest_dir = os.path.join(jars,"libraries","optifine","OptiFine",of_json_name )
    mkdir_p( optifine_dest_dir )

    print 'Checking Optifine...'
    optifine_jar = "OptiFine-"+of_json_name+".jar"
    optifine_dest_file = os.path.join( optifine_dest_dir, optifine_jar )
 
    download_optifine = False
    optifine_md5 = ''
    if not is_non_zero_file( optifine_dest_file ):
        download_optifine = True
    else:
        optifine_md5 = get_md5( optifine_dest_file )
        print 'Optifine md5: %s' % optifine_md5
        if optifine_md5 != of_file_md5:
            download_optifine = True
            print 'Bad MD5!'
        else:
            print 'MD5 good!'
    
    if download_optifine: 
        # Use optifine filename for URL
        optifine_url = "http://optifine.net/download.php?f=OptiFine_"+of_file_name+of_file_extension
        print 'Downloading Optifine...'
        if not download_file( optifine_url, optifine_dest_file, of_file_md5 ):
            print 'FAILED to download Optifine!'
            sys.exit(1)
        else:
            shutil.copy(optifine_dest_file,os.path.join(flat_lib_dir, os.path.basename(optifine_dest_file)))
            
    if of_file_md5 == "":
        optifine_md5 = get_md5( optifine_dest_file )
        print 'Optifine md5: %s' % optifine_md5
        sys.exit(0)

    json_obj = []
    with open(source_json_file,"rb") as f:
        #data=f.read()
        #print 'JSON File:\n%s' % data
        json_obj = json.load( f )
    try:
        newlibs = []
        for lib in json_obj['libraries']:
            libname = lib["name"]
            skip = False
            if "rules" in  lib:
                for rule in lib["rules"]:
                    if "action" in rule and rule["action"] == "allow" and "os" in rule:
                        skip = True
                        for entry in rule["os"]:
                            if "name" in entry:
                                if rule["os"]["name"] == native:
                                    skip = False

            if skip:
                print 'File: %s\nSkipping due to rules' % libname
                continue
                
            group,artifact,version = lib["name"].split(":")
            if "url" in lib:
                repo = lib["url"]
            else:
                repo = "https://libraries.minecraft.net/"

            if "natives" in lib:
                url = group.replace(".","/")+ "/"+artifact+"/"+version +"/"+artifact+"-"+version+"-"+lib["natives"][native]+".jar"
            else:
                url = group.replace(".","/")+ "/"+artifact+"/"+version +"/"+artifact+"-"+version+".jar"

            index = url.find('${arch}')
            if index > -1:
                # Get both 32 and 64 bit versions
                url32 = url.replace('${arch}', '32')
                file32 = os.path.join(jars,"libraries",url32.replace("/",os.sep))
                mkdir_p(os.path.dirname(file32))
                download_file( repo + url32, file32 )
                shutil.copy(file32,os.path.join(flat_lib_dir, os.path.basename(file32)))
                
                url64 = url.replace('${arch}', '64')
                file64 = os.path.join(jars,"libraries",url64.replace("/",os.sep))
                mkdir_p(os.path.dirname(file64))
                download_file(repo + url64, file64)
                shutil.copy(file64,os.path.join(flat_lib_dir, os.path.basename(file64)))                

                # Use preferred architecture to choose which natives to extract.
                if preferredarch is '32':
                    print '    Using preferred arch 32bit'
                    extractnatives( lib, jars, file32, flat_native_dir )
                else:
                    print '    Using preferred arch 64bit'
                    extractnatives( lib, jars, file64, flat_native_dir )                
               
            else:
                file = os.path.join(jars,"libraries",url.replace("/",os.sep))
                mkdir_p(os.path.dirname(file))
                if download_file( repo + url, file ) == True:
                    shutil.copy(file,os.path.join(flat_lib_dir, os.path.basename(file)))  
                    extractnatives( lib, jars, file, flat_native_dir )
                
            newlibs.append( lib )
        json_obj['libraries'] = newlibs
        if forgedep is False:
            with open(json_file,"wb+") as f:
                json.dump( json_obj,f, indent=1 )
    except Exception as e:
        print 'ERROR: %s' % e
        raise

    if download_mc == True:
        repo = "https://s3.amazonaws.com/Minecraft.Download/"
        jar_file = os.path.join(versions,mc_version+".jar")
        jar_url = repo + "versions/"+mc_version+"/"+mc_version+".jar"
        download_file( jar_url, jar_file, mc_file_md5 )
        shutil.copy(jar_file,os.path.join(flat_lib_dir, os.path.basename(jar_file))) 
        
        if mc_file_md5 == "":
            mc_md5 = get_md5( jar_file )
            print '%s md5: %s' % ( os.path.basename(jar_file), mc_md5 )
            sys.exit(0)	

def extractnatives( lib, jars, file, copydestdir ):
    if "natives" in lib:
        folder = os.path.join(jars,"versions",mc_version,mc_version+"-natives")
        mkdir_p(folder)
        zip = zipfile.ZipFile(file)
        #print 'Native extraction: folder: %s, file to unzip: %s' % (folder, file)
        for name in zip.namelist():
            if not name.startswith('META-INF') and not name.endswith('/'):
                out_file = os.path.join(folder, name)
                print '    Extracting native library %s' % name
                out = open(out_file, 'wb')
                out.write(zip.read(name))
                out.flush()
                out.close()
                shutil.copy(out_file,os.path.join(copydestdir, os.path.basename(out_file))) 

def zipmerge( target_file, source_file ):
    out_file, out_filename = tempfile.mkstemp()
    out = zipfile.ZipFile(out_filename,'a')
    try:
        target = zipfile.ZipFile( target_file, 'r')
    except Exception as e:
        print 'zipmerge: target not a zip-file: %s' % target_file
        raise

    try:        
        source = zipfile.ZipFile( source_file, 'r' )
    except Exception as e:
        print 'zipmerge: source not a zip-file: %s' % source_file
        raise
        
    #source supersedes target
    source_files = set( source.namelist() )
    target_files = set( target.namelist() ) - source_files

    for file in source_files:
        out.writestr( file, source.open( file ).read() )

    for file in target_files:
        out.writestr( file, target.open( file ).read() )

    source.close()
    target.close()
    out.close()
    os.remove( target_file )
    shutil.copy( out_filename, target_file )


def symlink(source, link_name):
    import os
    os_symlink = getattr(os, "symlink", None)
    if callable(os_symlink):
        try:
            os_symlink(source, link_name)
        except Exception:
            pass
    else:
        import ctypes
        csl = ctypes.windll.kernel32.CreateSymbolicLinkW
        csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        csl.restype = ctypes.c_ubyte
        flags = 1 if os.path.isdir(source) else 0
        if csl(link_name, source, flags) == 0:
            raise ctypes.WinError()

def osArch():
    if platform.machine().endswith('64'):
        return '64'
    else:
        return '32'

def main(mcp_dir):
    print 'Using base dir: %s' % base_dir
    print 'Using mcp dir: %s (use -m <mcp-dir> to change)' % mcp_dir
    print 'Preferred architecture: %sbit - preferring %sbit native extraction (use -a 32 or -a 64 to change)' % (preferredarch, preferredarch)
    if dependenciesOnly:
        print 'Downloading dependencies ONLY'
    else:
        if nomerge is True:
            print 'NO Optifine merging'
        if nocompilefixpatch is True:
            print 'SKIPPING Apply compile fix patches'
        if nopatch is True:
            print 'SKIPPING Apply Minecrift patches'
        
    if clean == True:
        print 'Cleaning...'
        if force == False:
            print ''
            print 'WARNING:'
            print 'The clean option will delete all folders created by MCP, including the'
            print 'src folder which may contain changes you made to the code, along with any'
            print 'saved worlds from the client or server.'
            print 'Minecrift downloaded dependencies will also be removed and re-downloaded.'
            print 'Patches will be left alone however.'
            answer = raw_input('If you really want to clean up, enter "Yes" ')
            if answer.lower() not in ['yes']:
                print 'You have not entered "Yes", aborting the clean up process'
                sys.exit(1)        
        print 'Cleaning mcp dir...'
        reallyrmtree(mcp_dir)
        print 'Cleaning lib dir...'
        reallyrmtree(os.path.join(base_dir,'lib'))
        print 'Cleaning patchsrc dir...'
        reallyrmtree(os.path.join(base_dir,'patchsrc'))
        print 'Installing mcp...'
        installAndPatchMcp(mcp_dir)


    print("\nDownloading dependencies...")
    download_deps( mcp_dir, True, True ) # Forge libs
    download_deps( mcp_dir, True, False ) # Vanilla libs
    if dependenciesOnly:
        sys.exit(1)

    if nomerge == False:
        print("Applying Optifine...")
        optifine = os.path.join(mcp_dir,"jars","libraries","optifine","OptiFine",of_json_name,"OptiFine-"+of_json_name+".jar" )
        minecraft_jar = os.path.join( mcp_dir,"jars","versions",mc_version,mc_version+".jar")
        print ' Merging\n  %s\n into\n  %s' % (optifine, minecraft_jar)
        zipmerge( minecraft_jar, optifine )
    else:
        print("Skipping Optifine merge!")
    
    print("Decompiling...")
    src_dir = os.path.join(mcp_dir, "src","minecraft")
    if os.path.exists( src_dir ):
        shutil.rmtree( src_dir, True )
    sys.path.append(mcp_dir)
    os.chdir(mcp_dir)
    from runtime.decompile import decompile
    #         Conf  JAD    CSV    -r     -d     -a     -n     -p     -o     -l     -g     -c    -s     --rg   -w    json  --nocopy
    decompile(None, False, False, False, False, False, False, False, False, False, False, True, False, False, None, None, True  )

    os.chdir( base_dir )

    # Create original decompile src dir
    org_src_dir = os.path.join(mcp_dir, "src",".minecraft_orig")
    if os.path.exists( org_src_dir ):
        shutil.rmtree( org_src_dir, True )
    shutil.copytree( src_dir, org_src_dir )

    if nocompilefixpatch == False:
        compile_error_patching_done = False
        
        # Patch stage 1: apply only the patches needed to correct the
        # optifine merge decompile errors
        mcp_patch_dir = os.path.join( base_dir, "mcppatches", "patches" )
        if os.path.exists( mcp_patch_dir ):
            print("Patching Optifine merge decompile errors...")
            applychanges( mcp_dir, patch_dir="mcppatches/patches", backup=False, copyOriginal=False, mergeInNew=False )
            compile_error_patching_done = True
        
        # Address problem files - copy over directly
        problem_file_dir = os.path.join( base_dir, "mcppatches", "problemfiles" )
        if os.path.exists( problem_file_dir ):
            print("Addressing problem files...")        
            xp_problem_file = os.path.join(problem_file_dir, "xp.java")
            shutil.copy( xp_problem_file, os.path.join( mcp_dir, "src", "minecraft", "net", "minecraft", "src", "xp.java" ) )
            chunkrenderdispatcher_problem_file = os.path.join(problem_file_dir, "ChunkRenderDispatcher.java")
            shutil.copy( chunkrenderdispatcher_problem_file, os.path.join( mcp_dir, "src", "minecraft", "net", "minecraft", "client", "renderer", "chunk", "ChunkRenderDispatcher.java" ) )
            compile_error_patching_done = True

        # Update the client md5
        if compile_error_patching_done == True:
            print("Updating client.md5...")
            os.chdir(mcp_dir)
            from runtime.updatemd5 import updatemd5
            updatemd5( None, True, True, False )
            os.chdir( base_dir )

            # Now re-create the .minecraft_orig with the new buildable state
            if os.path.exists( org_src_dir ):
                shutil.rmtree( org_src_dir, True )
                shutil.copytree( src_dir, org_src_dir )
                
    if nopatch == False:
        # Patch stage 2: Now apply our main Minecrift patches, only
        # changes needed for Minecrift functionality
        print("Applying full Minecrift patches...")
        applychanges( mcp_dir )
    else:
        print("Apply patches skipped!")

def reallyrmtree(path):
    if not sys.platform.startswith('win'):
        if os.path.exists(path):
            shutil.rmtree(path)
    else:
        i = 0
        try:
            while os.stat(path) and i < 20:
                shutil.rmtree(path, onerror=rmtree_onerror)
                i += 1
        except OSError:
            pass

        # raise OSError if the path still exists even after trying really hard
        try:
            os.stat(path)
        except OSError:
            pass
        else:
            raise OSError(errno.EPERM, "Failed to remove: '" + path + "'", path)

def rmtree_onerror(func, path, _):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
    time.sleep(0.5)
    try:
        func(path)
    except OSError:
        pass
        
def replacelineinfile(file_path, pattern, subst, firstmatchonly=False):
    #Create temp file
    fh, abs_path = mkstemp()
    new_file = open(abs_path,'wb')
    old_file = open(file_path,'rb')
    hit = False
    for line in old_file:
        if pattern in line and not (firstmatchonly == True and hit == True): 
            new_file.write(subst)
            hit = True
        else:
            new_file.write(line)
    #close temp file
    new_file.close()
    close(fh)
    old_file.close()
    #Remove original file
    remove(file_path)
    #Move new file
    move(abs_path, file_path)
    
if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-o', '--no-optifine', dest='nomerge', default=False, action='store_true', help='If specified, no optifine merge will be carried out')
    parser.add_option('-c', '--clean', dest='clean', default=False, action='store_true', help='Cleans the mcp dir, and REMOVES ALL SOURCE IN THE MCPxxx/SRC dir. Re-downloads dependencies')
    parser.add_option('-f', '--force', dest='force', default=False, action='store_true', help='Forces any changes without prompts')
    parser.add_option('-d', '--dependenciesOnly', dest='dep', default=False, action='store_true', help='Gets the dependencies only - no merge, compile or apply changes are performed.')
    parser.add_option('-n', '--no-patch', dest='nopatch', default=False, action='store_true', help='If specified, no patches will be applied at the end of installation')
    parser.add_option('-x', '--no-fix-patch', dest='nocompilefixpatch', default=False, action='store_true', help='If specified, no compile fix patches will be applied at the end of installation')
    parser.add_option('-m', '--mcp-dir', action='store', dest='mcp_dir', help='Path to MCP to use', default=None)
    parser.add_option('-a', '--architecture', action='store', dest='arch', help='Architecture to use (\'32\' or \'64\'); prefer 32 or 64bit dlls', default=None)
    options, _ = parser.parse_args()

    if not options.arch is None:
        if options.arch is '32':
            preferredarch = '32'
        elif options.arch is '64':
            preferredarch = '64'
            
    if preferredarch is '':
        preferredarch = osArch()

        
    nomerge = options.nomerge
    nopatch = options.nopatch
    nocompilefixpatch = options.nocompilefixpatch
    clean = options.clean
    force = options.force
    dependenciesOnly = options.dep
    
    if not options.mcp_dir is None:
        main(os.path.abspath(options.mcp_dir))
    elif os.path.isfile(os.path.join('..', 'runtime', 'commands.py')):
        main(os.path.abspath('..'))
    else:
        main(os.path.abspath(mcp_version))

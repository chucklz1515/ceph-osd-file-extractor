import os
from pathlib import Path
import re
import shutil

# ####################################################################################################
# some alignment vars

filenameDefinitionLength = 0x02
unknownDefinition1Length = 0x02
null2Length = 0x02
unknownDefinition2Length = 0x04
null1Length = 0x01
continueReadingLength = 0x01
#null2Length = 0x02
numberOfDirectoryNamesLength = 0x01
null3Length = 0x03
#filenameDefinitionLength = 0x02
unknownDefinition3Length = 0x02
#null2Length = 0x02
unknownDefinition4Length = 0x04
#null1Length = 0x01
#continueReadingLength = 0x01
#null2Length = 0x02
fileNameLengthLength = 0x01
#null3Length = 0x03
#fileNameLength = 0x??
unknownDefinition5Length = 0x02
unknownDefinition6Length = 0x02
null4Length = 0x04
fileTypeLength = 0x01

# this to help convert a byte to a bool (b'\x00' = 0, else = 1)
byteCompareForBool = b'\x00'

# when reading the file type, these are the types ive observed
fileTypeMappingFile = b'\x05'
fileTypeMappingDir = b'\x04'

# ####################################################################################################
# walk through the filesystem
#testFileAttrName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/attr/_parent'
#testFileDataName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/data'
testFileAttrName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/attr/_parent'
testFileDataName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/data'

# fuse mounted osd path
#testRoot = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#'
testRoot = '/mnt/test/5.7f_head/all/#5:fea38466:::100028f0fe1.00000000:head#'
fuseRoot = '/mnt/test'

# destination dirs
mntDir = '/mnt'
destRoot = 'ceph-fs-storage'

# exclusions. mostly to exclude the metadata dir
exclusionDirs = ('/mnt/test/meta')

# for selecting the folder and grabbing relative files
relativeFolderStructureDir = '/attr'
folderStructureFile = '_parent'
dataFilename = 'data'

# placement group indicator extractor
placementGroupNameRegex = '(#.*?):+(.*?):+(.*?)\.(.*?):+(.*?)#$'
#                           g1      g2     g3     g4     g5

# determine number of paths to loop
#fuseRootDirs = os.walk(testRoot)
fuseRootDirs = os.walk(fuseRoot)

# walk through the fuse-mounted OSD
#for fullPaths in fuseRootDirs:
for fullPaths, _, _ in fuseRootDirs:
    # dont walk into excluded dirs
    if not exclusionDirs in fullPaths:
        # only walk into dirs which are attr dir
        if fullPaths.endswith(relativeFolderStructureDir):
            # at this point we've got the dirs we want
            # now we can walk up 1 dir for the (assumed) placement group's main dir
            pgMainDir = os.path.normpath(os.path.dirname(fullPaths))
            
            # join up the main dir with the folder structure file
            pgFolderStructureFile = os.path.normpath(os.path.join(pgMainDir, relativeFolderStructureDir[1:], folderStructureFile))
            
            # extract the file's unique reference
            pgDataFileRegexSearch = re.search(placementGroupNameRegex, Path(pgFolderStructureFile).parent.parent.name)
            
            # only proceed if a match has been made. this means that there _is_ a data file to grab
            if pgDataFileRegexSearch:
                pgDataFileUniqueIndicator = pgDataFileRegexSearch.group(3)
                pgDataFileChunk = int(pgDataFileRegexSearch.group(4), 16)
                
                # only proceed if the folder structure file exists
                if os.path.exists(pgFolderStructureFile):
                    # join up the main dir with the data file
                    pgDataFile = os.path.normpath(os.path.join(pgMainDir, dataFilename))
                    
                    # only proceed if the data file exists
                    if os.path.exists(pgDataFile):
                        # ####################################################################################################
                        # running the loop to scrape the file/folder structure
                        
                        # empty list for saving the path details
                        filePathInformation = []
                        
                        # open the file readonly as a binary file
                        with open(pgFolderStructureFile, mode='rb') as file:
                            # get EOF seek address - seek to 0 bytes from the end of file (2)
                            file.seek(0, 2)
                            eofAddress = file.tell()
                            
                            # return to beginning of file - seek to 0 bytes from the beginning of file (0)
                            file.seek(0, 0)
                            
                            # _parent file header
                            startDefinition = file.read(filenameDefinitionLength)
                            #print(startDefinition.hex(' '))
                            #todo: ensure that this value is 0x05 0x04
                            
                            # unknown block 1
                            unknownDefinition1 = file.read(unknownDefinition1Length)
                            #print(unknownDefinition1.hex(' '))
                            
                            # null with length 2
                            file.read(null2Length)
                            
                            # unknown block 2
                            unknownDefinition2 = file.read(unknownDefinition2Length)
                            #print(unknownDefinition2.hex(' '))
                            
                            # null with length 1
                            file.read(null1Length)
                            
                            # continue reading byte
                            continueReading = file.read(continueReadingLength) != byteCompareForBool
                            #print(continueReading)
                            #todo: it should always be 0x01 here as we are in the header
                            
                            # null with length 2
                            file.read(null2Length)
                            
                            # number of directory names in path
                            numberOfDirectoryNames = file.read(numberOfDirectoryNamesLength)
                            #print(numberOfDirectoryNames.hex(' '))
                            
                            # null with length 3
                            file.read(null3Length)
                            
                            # seek through the binary file until our seek cursor is at the end of the file
                            #while(file.tell() < eofAddress):
                            while(file.tell() < eofAddress and continueReading):
                                # file header
                                startFileDefinition = file.read(filenameDefinitionLength)
                                #print(startFileDefinition.hex(' '))
                                #todo: ensure that this value is 0x02 0x02
                                
                                # unknown block 3
                                unknownDefinition3 = file.read(unknownDefinition3Length)
                                #print(unknownDefinition3.hex(' '))
                                
                                # null with length 2
                                file.read(null2Length)
                                
                                # unknown block 4
                                unknownDefinition4 = file.read(unknownDefinition4Length)
                                #print(unknownDefinition4.hex(' '))
                                
                                # null with length 1
                                file.read(null1Length)
                                
                                # continue reading byte
                                continueReading = file.read(continueReadingLength) != byteCompareForBool
                                #print(continueReading)
                                # this should stop the loop after reading the last file path
                                
                                # null with length 2
                                file.read(null2Length)
                                
                                # length of the filename
                                fileNameLength = file.read(fileNameLengthLength)
                                #print(fileNameLength.hex(' '))
                                
                                # null with length 3
                                file.read(null3Length)
                                
                                # this is the filename. read length is based on above length of filename
                                fileName = file.read(int.from_bytes(fileNameLength)).decode('utf-8')
                                #print(fileName)
                                
                                # append the file name that we have captured to a list
                                if fileName:
                                    filePathInformation.append(fileName)
                                
                                # unknown block 5
                                unknownDefinition5 = file.read(unknownDefinition5Length)
                                #print(unknownDefinition5.hex(' '))
                                
                                # unknown block 6
                                unknownDefinition6 = file.read(unknownDefinition6Length)
                                #print(unknownDefinition6.hex(' '))
                                
                                # null with length 4
                                file.read(null4Length)
                        
                            # after the loop, we have 1 final area to check and that is the item type
                            fileType = file.read(fileTypeLength)
                            #print(fileType.hex(' '))
                        
                        # ####################################################################################################
                        # handling the filename with the data file
                        
                        # add root dirs
                        filePathInformation.append(destRoot)
                        filePathInformation.append(mntDir)
                        
                        # first reverse the list so that it is easier to create dir structure
                        filePathInformation.reverse()
                        
                        # joins up all the dirs with the destination root dir. excludes filename
                        newDir = os.path.normpath(os.path.join(*filePathInformation[:-1]))
                        #print(newDir)
                        
                        newFile = os.path.normpath(os.path.join(*filePathInformation))
                        #print(newFile)
                        
                        # ####################################################################################################
                        # FILE RECOVERY
                        
                        # if it is a directory, make that directory!
                        if fileType == fileTypeMappingDir:
                            if not os.path.exists(newFile):
                                print('new dir:  ' + newFile)
                                os.makedirs(newFile)
                        
                        # if it is a file, copy that file!
                        if fileType == fileTypeMappingFile:
                            if not os.path.exists(newFile):
                            #if os.path.exists(newFile):
                                if not os.path.exists(newDir):
                                    print('new dir:  ' + newDir)
                                    os.makedirs(newDir)
                                
                                print('old file: ' + pgDataFile)
                                print('new file: ' + newFile)
                                shutil.copyfile(pgDataFile, newFile)
                                
                                #NEW BUG ALERT: files over 4096KB are TRUNCATED! likely means that the files were ripped into pieces
                                # RIP MY FILES INTO PIECES
                                # THIS IS MY LAST RESTORE
                                
                                # if the file is 4MB, then we must also check if it has been chunked
                                if os.stat(pgDataFile).st_size == 4194304:
                                    listOfPgDataFileChunkPaths = []
                                    
                                    print('data file size is 4MB. checking if chunked...')
                                    
                                    # search for the placement group's file identifier in other placement groups
                                    #WARNING: this process is SLOW as i have to re-scan the whole dir
                                    #for pgDataFileUniqueIndicatorFullPaths in fuseRootDirs:
                                    for pgDataFileUniqueIndicatorFullPaths, _, _ in fuseRootDirs:
                                        # only walk into dirs which contain the file's unique identifier
                                        if pgDataFileUniqueIndicator in pgDataFileUniqueIndicatorFullPaths:
                                            listOfPgDataFileChunkPaths.append(os.path.normpath(pgDataFileUniqueIndicatorFullPaths))
                                    
                                    # count the number of directories found. logic:
                                    
                                    # if the number of chunked files found is only 1, then it really _is_ a 4MB file
                                    if len(listOfPgDataFileChunkPaths) == 1:
                                        print('data file not chunked')
                                    
                                    #  if there are more than 1 dir found, then append the data to the already-written file (above)
                                    if len(listOfPgDataFileChunkPaths) > 1:
                                        print('chunked data file found!')
                                        
                                        # iterate over the list of file chunk paths
                                        for pgDataFileChunkPath in listOfPgDataFileChunkPaths:
                                            
                                            # increase the chunk iterator
                                            pgDataFileChunk += 1
                                            
                                            # convert it to a hex string (for searching the directory names)
                                            pgDataFileChunkString = (f'{pgDataFileChunk:0>8x}')
                                            
                                            # loop through the list (again) and filter by current chunk
                                            for pgDataFileChunkPath2 in listOfPgDataFileChunkPaths:
                                                if pgDataFileChunkString in pgDataFileChunkPath2:
                                                    
                                                    # this gets the main dir of the data chunk file
                                                    pgDataChunkMainDir = os.path.normpath(os.path.dirname(pgDataFileChunkPath2))
                                                    
                                                    # this gets the path of the dat achunk file
                                                    pgDataChunkFile = os.path.normpath(os.path.join(pgDataChunkMainDir, dataFilename))
                                                    
                                                    #print(pgDataChunkFile)
                                                    print(pgDataFileChunkPath2)
                                                    
                                                    # read the file's chunk data file
                                                    with open(pgDataChunkFile, 'rb') as pgDataFileChunkDataFile_file:
                                                        # write to the file in append binary mode
                                                        with open(newFile, 'ab') as newFile_file:
                                                            #print('reading from: ' + pgDataChunkFile)
                                                            newFile_file.write(pgDataFileChunkDataFile_file.read())

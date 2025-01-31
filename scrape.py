import os
import shutil

# ####################################################################################################
# some alignment vars
offsetRelativeAddressCorrection = 0x01

startOfFirstFilenameDefinitionAddress = 0x12
filenameDefinitionLength = 0x02
relativeFilePermissionsAddress = 0x01 - offsetRelativeAddressCorrection
filePermissionsLength = 0x02
relativeFileDateAddress = 0x03 - offsetRelativeAddressCorrection
fileDateLength = 0x04
relativeTrueAddress = 0x02 - offsetRelativeAddressCorrection
trueLength = 0x01
relativeFileNameLengthAddress = 0x03 - offsetRelativeAddressCorrection
fileNameLengthLength = 0x01
relativeFileNameAddress = 0x04 - offsetRelativeAddressCorrection
#fileNameLength = 0x01 # this is captured dynamically within the _parent file read loop
relativeNextFileDefinitionAddress = 0x09 - offsetRelativeAddressCorrection

# ####################################################################################################
# walk through the filesystem

# these are test paths
testFileAttrName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/attr/_parent'
testFileDataName = '/mnt/test/5.f_head/all/#5:f1988779:::10002413871.00000000:head#/data'

# fuse mounted osd path
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

# walk through the fuse-mounted OSD
for fullPaths, dirNames, fileNames in os.walk(fuseRoot):
    # dont walk into excluded dirs
    if not exclusionDirs in fullPaths:
        # only walk into dirs which are attr dir
        if fullPaths.endswith(relativeFolderStructureDir):
            # at this point we've got the dirs we want
            
            # now we can walk up 1 dir for the (assumed) placement group's main dir
            pgMainDir = os.path.normpath(os.path.dirname(fullPaths))
            
            # join up the main dir with the folder structure file
            pgFolderStructureFile = os.path.normpath(os.path.join(pgMainDir, relativeFolderStructureDir[1:], folderStructureFile))
            
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
                        
                        # at the start of the file, we will load up the first address
                        file.seek(startOfFirstFilenameDefinitionAddress, 0)
                        
                        # seek through the binary file until our seek cursor is at the end of the file
                        while(file.tell() < eofAddress):
                            file.read(filenameDefinitionLength).hex(' ')
                            #print(file.read(filenameDefinitionLength).hex(' '))
                            #todo: ensure that this value is 0x02 0x02
                            
                            #todo: not sure if this the permission value
                            file.seek(relativeFilePermissionsAddress, 1)
                            file.read(filePermissionsLength).hex(' ')
                            #print(file.read(filePermissionsLength).hex(' '))
                            
                            #todo: not sure if this is the date value
                            file.seek(relativeFileDateAddress, 1)
                            file.read(fileDateLength).hex(' ')
                            #print(file.read(fileDateLength).hex(' '))
                            
                            #todo: this _appears_ to be always true byte (ie. 0x01). perhaps it is a alignment byte?
                            file.seek(relativeTrueAddress, 1)
                            file.read(trueLength).hex(' ')
                            #print(file.read(trueLength).hex(' '))
                            #todo: ensure that this value is 0x01
                            
                            file.seek(relativeFileNameLengthAddress, 1)
                            fileNameLength = file.read(fileNameLengthLength)
                            #print(fileNameLength.hex(' '))
                            
                            file.seek(relativeFileNameAddress, 1)
                            fileName = file.read(int.from_bytes(fileNameLength)).decode('utf-8')
                            #print(fileName)
                            
                            # append the file name that we have captured to a list
                            if fileName:
                                filePathInformation.append(fileName)
                            
                            # move to the next file/dir name definition
                            file.seek(relativeNextFileDefinitionAddress, 1)
                    
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
                    
                    # make that dir
                    if not os.path.exists(newDir):
                        os.makedirs(newDir)
                        
                    # copy the data file to the fullpath file
                    if not os.path.exists(newFile):
                        shutil.copyfile(pgDataFile, newFile)

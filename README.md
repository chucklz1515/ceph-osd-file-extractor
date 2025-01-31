# ceph-osd-file-extractor
This is a python script which will extract files from a fuse-mounted ceph OSD.

# Background
I have a home lab and run a docker swarm across 3 Linux (Debian) nodes. The nodes also have a ceph cluster serving a CephFS. The CephFS uses a pool which has x3 replication (in my head, this means that each node has a 100% copy of the data - I'm sure this logic is incorrect). I mount the CephFS to: `/mnt/ceph-fs-storage` on each node. The docker containers use this to bind volumes. This means that the docker swarm is able to place a container on any node and it has access to the data to mount.

Now, I'm not rocking a 45 drives rack or anything. I have these [ODROID H-3](https://www.hardkernel.com/shop/odroid-h3/) computers. They are quite beefy: 4CPUs, 64GB RAM, and I put a 1TB Samsung m.2 SSD in it.

The trouble is: I don't have external disks.

So, I created them, _virtually_:
```
# run below on each node

# 206GB empty file
dd if=/dev/zero of=/vdisk/ceph01 bs=100M count=2100

# bind that empty file as a block device using loop
losetup /dev/loop0 /vdisk/ceph01

# create LVM volume group on the loop device
vgcreate cephVolGrp /dev/loop0

# create LVM volume in the group
lvcreate -n cephVol01 -L 200g cephVolGrp

# backup the LVM config - no seriously, DO THIS
vgcfgbackup -f /root/cephVolGrp-cephVol01
```

Now I have a logical block volume on the server that I can use for OSD data. Note that ceph, rightfully, doesn't present it when scanning for disks. Instead, I have to add it manually. But it still works fine:
```
ceph orch daemon add osd node01:/dev/cephVolGrp/cephVol01
ceph orch daemon add osd node02:/dev/cephVolGrp/cephVol01
ceph orch daemon add osd node03:/dev/cephVolGrp/cephVol01
```

I recently encountered a failure with my ceph cluster. I'm accepting blame as it was 100% my fault for various reasons:
 * Used debian's main repo for ceph packages (should use ceph's repo instead).
 * Failed to upgrade ceph. Was running v16-pacific instead of v18-reef (which was latest/stable at the time I build the cluster too...).
 * Was running old ceph (v16-pacific) on Debian Bookworm (old binaries _should_ not have even worked).
 * Followed ceph's documentation for setting up a cluster. I'll only take half-blame here as their documentation is:
   * Moderately lacking in relavent information - There are lots of commands that are out-of-date or unsupported. Some commands require being executed in podman/docker containers (without indicating as such in the docs).
   * Failed to convey the importance of their cluster setup configurations.
 * Upon realizing I was out-of-date, I switched to their package repo and upgraded from 16-pacific to 18-reef without any consideration.
 * Destroyed my cluster without backing up configurations (except I did backup /var/lib/ceph, though it didn't matter).
 * Not backing up my data.

That said, there were some saving graces:
 * I didn't encrypt my cluster/OSDs. I likely would not be able to recover if I encrypted them.
 * My disks were still "good". Meaning I didn't have a hardware failure.
 * The ceph tooling allowed the ability to fuse-mount an OSD. More on this below.

# Time Taken
I spent around 36 hours troubleshooting and effectively _becoming_ a ceph master (journeyman?) simply by trying to recover my cluster. I want to make this repo a point where ceph noobs can come for a sliver of hope in recovering their data.

# Considerations
Obviously, the holy grail recovery would be to magically do _something_ where my ceph cluster comes back. However, this is likely not going to happen. Instead, I set myself up with some realistic goals in descending order of hope (which, coincidentally, is increasing order of likelyhood):
 * I want to setup a new ceph cluster and re-attach the old OSDs
 * I want to setup a new ceph cluster with new OSDs and clone the data from the old OSDs.
 * I want to extract my files from my old OSDs into a new filesystem.
 * I want to extract file contents from my old OSDs.
 * I want to get my documents/pictures back :(

# Troubleshooting Journey
I spent 60% of those 36 hours trying to re-import the old OSDs into either (none of which worked BTW):

## Recreation of the old ceph cluster
```
:'(
```

## New ceph cluster with _same_ cluster GUID (ie. re-use old cluster's fsid)
```
# bootstrap new cluster with old cluster's fsid
#NOTE: make sure to move the /var/lib/ceph/d8c1c426-cf4c-11ee-aa6f-001e06453165 dir to a new name: /var/lib/ceph/d8c1c426-cf4c-11ee-aa6f-001e06453165_orig
cephadm bootstrap \
--fsid d8c1c426-cf4c-11ee-aa6f-001e06453165 \
--allow-overwrite \
--mon-ip 192.168.60.4 \
--cluster-network 192.168.60.0/24 \
--skip-mon-network \
--skip-ssh;

# ... skipping other ceph cluster setup details ...

# now try to activate the OSDs on each node:

# node 01 - had osd.0 with an osd fsid 9f570bd7-ea93-44ff-9628-67a9c0a05b51
ceph-volume lvm activate 0 9f570bd7-ea93-44ff-9628-67a9c0a05b51

# node 02 - had osd.1 with an osd fsid 66e38bde-3ee3-46ba-ad01-2201e534fdea
ceph-volume lvm activate 1 66e38bde-3ee3-46ba-ad01-2201e534fdea

# node 03 - had osd.2 with an osd fsid dbe70c6f-f235-4616-ae48-a47839355eb6
ceph-volume lvm activate 2 dbe70c6f-f235-4616-ae48-a47839355eb6
```

## Brand new shiny ceph cluster (ie. new cluster fsid)
```
# bootstrap new cluster with new cluster fsid
cephadm bootstrap \
--allow-overwrite \
--mon-ip 192.168.60.4 \
--cluster-network 192.168.60.0/24 \
--skip-mon-network \
--skip-ssh;

# try to adopt old OSDs on each node:

# node 01
cephadm adopt --style legacy --name osd.0

# node 02
cephadm adopt --style legacy --name osd.1

# node 03
cephadm adopt --style legacy --name osd.2
```

I spend the remaining 40% simply trying to recover the files. Since I was using this ceph cluster to store files for docker mounts, they are simple "files" and nothing crazy like sym/hardlinks, etc. This makes recovery _easier_ (again, in my head).

## First up
It seems that, no, you cannot simply browse the OSDs. The way that ceph OSDs work (to my understanding) is that it doesnt create a filesystem as you know it. Yes, the "filesystem" is called Bluestore and it is a really real file system, but tools like (g)parted can't read it. So I have to rely on ceph tooling. 

### OR DO I?
```
> binwalk /dev/cephVolGrp/cephVol01

DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
6160384       0x5E0000        JPEG image data, EXIF standard
6160396       0x5E000C        TIFF image data, little-endian offset of first image directory: 8
...
```

Yay! I see file markers! That means I should be able to extract them right?
```
> binwalk -e /dev/cephVolGrp/cephVol01
<results in a 200GB zlib file>
```

...okay, that's not what I was expecting. Oh! maybe the OSD was compressed and I have a compressed file. Let's try to decompress it!
```
> pigz -dc _extracted/file.zlib
<results in a 200GB uncompressed file
```

...there's no files here are there?

### I DO!
I knew I would fall into a recurring pattern of extracting/decompressing possible scenarios when that may not even be whats happening. I also couldn't garuntee that I would have filenames or paths. I really needed all 3:
 * data
 * filename
 * path

I don't care _too_ much about file owner/permissions or modified date. If i get it, then bonus. But often times the docker services will perform all relavent commands to fix permissions when executing.

Enter: [ceph-objectstore-tool](https://docs.ceph.com/en/reef/man/8/ceph-objectstore-tool/)

This is a ceph tool that is used to work with OSDs. It is probably the tool I need to use to extract my files from an OSD. There are a few problems though:
 * Documentation is __severly__ lacking. I'm not kidding.
 * Half the commands will only work on OSDs that are already part of a cluster, which is exactly what I don't have.

There are a few command options that seem like they may be able to help me. Coincidentally, these are the commands with the _least_ documentation:
 * `--op fsck` and `--op repair` - I hoped that I simply needed to repair the OSD's filesystem to join it to my new cluster - nope
 * `--op export` - I was hoping this exports the files - it does not
 * `--op dup` - This was promising. This appears to duplicate an OSD. However, it requires the src and dest OSDs to have the __same__ OSD fsid... what?
   * NOTE: I did a bad thing and used a hexeditor to replace all references of the old OSD's fsid with the new OSD's fsid. It did not like it lol
 * `--op fuse` - This mounts the OSD to a mountpoint using fuse

__WAIT WHAT?__

You read that right folks. There is a way to mount the OSD using fuse. This is the __closest__ I have gotten to seeing my data!

```
ceph-objectstore-tool --no-mon-config --op fuse --data-path /var/lib/ceph/d8c1c426-cf4c-11ee-aa6f-001e06453165_orig/osd.2/ --mountpoint /mnt/test

ls -la /mnt/test
total 0
drwx------ 0 root root  0 Dec 31  1969 2.0_head
drwx------ 0 root root  0 Dec 31  1969 3.0_head
drwx------ 0 root root  0 Dec 31  1969 3.10_head
drwx------ 0 root root  0 Dec 31  1969 3.11_head
drwx------ 0 root root  0 Dec 31  1969 3.12_head
...
```

However, the fight is not over yet.

## The Fuse-Mounted OSD
I poked around a bit inside the fuse-mounted OSD. After a short while I was able to piece some things together:
 * The top-level folder names (ie. 2.0_head) _appear_ to be the placement group data.
 * There is a `_parent` binary file which explains the file's full path within the CephFS
 * There is a `data` binary file which is the file's data

Folder structure looks like this:
```
/mnt/test
     |
     +-3.4_head (i think this is the placement group)
       |
       +- all
          |
          +- #3:20000000::::head#
             |
             +- data (this is a binary file of the file's data)
             |
             +- attr
                |
                +- _parent (this is a binary file which contain's the file's full path within the CephFS)
```

Holy cow, I had my data!! The problem now is extracting it. I took a peek inside the `_parent` file. It looks something like this:
```
<redacted lol, I've included it as a file in this repo>
```

Using a hexeditor, I took a few hours to map out the binary file and how I can select each folder name. I'm still missing __a lot__, but I was able to determine the following:
 * There are "file/folder definition" blocks
 * The first block always starts at address `0x12`
 * The "file/folder definition" block always starts with a `0x02 0x02`. Address mappings from here are relative:
   * address `0x00 - 0x01`: beginning `0x02 0x02` block marker
   * address `0x03 - 0x04`: I thought the next 2 bytes were file permissions, but it wasn't consistant. ignoring for now
   * address `0x05 - 0x06`: this is 2 byte null: `0x00 0x00`
   * address `0x07 - 0x0A`: I thought these 4 bytes were date, but it wasn't consistant. ignoring for now
   * address `0x0B - 0x0B`: this is 1 byte null: `0x00`
   * address `0x0C - 0x0C`: "_the one true byte_" - my guess is that it is some kind of alignment byte: `0x01`
   * address `0x0D - 0x0E`: this is 2 byte null: `0x00 0x00`
   * address `0x0F - 0x0F`: this is the length of the file/folder name. it tells you how many bytes to select in the next area.
     * __EXAMPLE: `0x04` for file name that is 4 bytes long__
   * address `0x10 - 0x13`: this is 3 byte null: `0x00 0x00 0x00`
   * address `0x14 - 0x18`: this is the start of the file/folder name. its length is determined by the above result.
     * __NOTE: I'm using an example of 4 byte file name length__
   * address `0x19 - 0x19`: this byte is unknown. it has a value, but i didn't see any point in collecting it
   * address `0x1A - 0x23`: honestly, i didn't care for the information at this point. i had what i needed which was the file/folder names. Importantly, from this byte to the next file/folder definition block is 8 bytes
 * The "file/folder definition" blocks define the file's full path, but in reverse order (ie. file/parent/parent_parent/etc.../) so it needs to be reversed

After mapping it out, I then proceeded to write a python script that would:
 * Walk over each placement group folder (ie. 2.0_head)
   * NOTE: exclude the metadata folder: `/mnt/test/meta`
 * Find the `_parent` file in the `attr` directory
 * Scrape the file's full path information
 * Copy the data file to the new cluster with the path information

# Limitations/Known Issues
## Zero Byte Data Files
Once I ran the script to start scraping the data, I found that there were several cases where the script will crash due to an error similar to:
```
old file: /mnt/test/5.1b_head/all/#5:d8b4db0d:::1000009b975.00000000:head#/data
new file: /mnt/ceph-fs-storage/data/some_dir/some_file
Traceback (most recent call last):
  File "/root/scrape.py", line 158, in <module>
    shutil.copyfile(pgDataFile, newFile)
  File "/usr/lib/python3.11/shutil.py", line 258, in copyfile
    with open(dst, 'wb') as fdst:
         ^^^^^^^^^^^^^^^
NotADirectoryError: [Errno 20] Not a directory: '/mnt/ceph-fs-storage/data/some_dir/some_file'
```

This occurs when:
 * Previously, the script found a `_parent` and `data` file for `/mnt/ceph-fs-storage/data/some_dir`.
   * The `data` file had a size of 0 bytes.
   * The script created a __file__ at the path `'/mnt/ceph-fs-storage/data/some_dir`.
 * Now, the script is trying to create a file at `/mnt/ceph-fs-storage/data/some_dir/some_file` only to find that `some_dir` is a file and not a directory.

### Mitigations
For now, I just skip processing any `data` file that has a size of 0 bytes. I thought of 2 reasons why there are `data` files with size of 0 bytes:
 * It is not a file, but a (possibly empty?) folder
 * The file is empty

I'll handle them later as I'm focused on getting back online as fast as possible.

# Conclusion
I was able to successfully recover my files. Granted, they have no metadata (correct permissions, datetime, etc), but I haven't lost anything.

# Final Words
__BACKUP YOUR DATA YOU FOOLS!!!__

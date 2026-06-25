import sys
import mutagen

def get_audio_cover(path_str):
    try:
        f = mutagen.File(path_str)
        if f is None:
            return None
        
        # ID3 tags (MP3)
        if hasattr(f, 'tags') and f.tags is not None:
            # Check APIC frames for MP3
            for key in f.tags.keys():
                if key.startswith('APIC'):
                    apic = f.tags[key]
                    return apic.data
            
            # Check FLAC / OGG
            if hasattr(f.tags, 'pictures'):
                if f.tags.pictures:
                    return f.tags.pictures[0].data
                    
            # Check MP4 / M4A
            if 'covr' in f.tags:
                covrs = f.tags['covr']
                if covrs:
                    # Usually MP4Cover object which inherits from bytes
                    return bytes(covrs[0])
                    
    except Exception as e:
        print("Error:", e)
    return None

if __name__ == '__main__':
    data = get_audio_cover(sys.argv[1])
    if data:
        print(f"Found cover! Size: {len(data)} bytes")
    else:
        print("No cover found.")

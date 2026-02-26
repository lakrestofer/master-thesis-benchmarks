import csv
import matplotlib.pyplot as plt
from tqdm import tqdm
import hashlib

def string_to_hex_color(text: str) -> str:
    """
    Converts a string into a deterministic hex color code.
    Example: "hello" -> "#5d4140"
    """
    # Create SHA-256 hash of the string
    hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()
    
    # Use first 3 bytes for RGB
    r, g, b = hash_bytes[0], hash_bytes[1], hash_bytes[2]
    
    return f'#{r:02x}{g:02x}{b:02x}'

x = []
y = []
c = []
currentLevel = 0

with open('log.csv', newline='') as logfile:
    logreader = csv.reader(logfile, delimiter='\t')
    for row in tqdm(logreader):
        event = row[0]
        time = float(row[2]) / 1000000000

        if(event == 'COMPUTE_BEGIN'):
            currentLevel += 1
        elif(event == 'COMPUTE_END'):
            currentLevel -= 1
        x += [time]
        y += [currentLevel]
        c += [string_to_hex_color(event)]

print("Creating plot...")
plt.scatter(x, y, c=c)
print("Saving plot...")
# plt.savefig('result.png')
plt.show()
# V2V Extractor
Extracts presets from .vars

- Download the executable or use pyinstaller to build from source
- The executable is in the releases section

# Usage
- Double click the .exe
- Follow the prompts. You can do a single file, multiple files seperated by a space or point it at a folder containing many files.
- If the .exe isnt in the vam root folder it will just make some folders to put all the stuff it extracts.
- If you are in the folder it will place them accordingly
<br>
<br>


                   A single path to a var: 
![image](https://github.com/user-attachments/assets/2bae3d70-3ce7-4315-b9db-550289f0bd2b) <br><br>
<br>

                           
                  Multiple full paths to vars: 
![image](https://github.com/user-attachments/assets/61c51c92-5a72-48a1-85a8-350073c63dc0) <br>
<br>
                
                        
                A folder path containing vars: 
![image](https://github.com/user-attachments/assets/b3f8d3e8-8b11-485c-8bd7-c75b48abc702) <br>
<br>
<br>
<br>
###__Devs__###

Or If you want to build from source:
```
pip install pyinstaller
```
Then point pyinstaller at the included .spec by running:
```
pyinstaller extractor.spec
```
This will compile the .exe and place it in the dist folder

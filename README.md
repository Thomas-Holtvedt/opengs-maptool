<img width="350" height="350" alt="ogs-mt-logo" src="https://github.com/user-attachments/assets/d03854c8-c2e1-468f-9f8a-269f498d169c" />

# Open Grand Strategy - Map Tool 
The OpenGS Map Tool is a specialized utility designed to streamline the creation of map data for use in grand strategy games. 
Province and territory maps form the backbone of these games, defining the geographical regions that players interact with.

## Features
- Generate and Export province maps
- Generate and Export province data
- Generate and Export territory maps
- Generate and Export territory data

## Showcase
<img width="2200" height="2318" alt="image" src="https://github.com/user-attachments/assets/1ad0250a-0a50-4bbd-b616-0e215a7ed2bc" />
<img width="2200" height="2308" alt="image" src="https://github.com/user-attachments/assets/7afe9e4c-648d-4e63-9636-a8df47bfba27" />

## How to install
### Option 1 (Windows only):
1. "Releases" section in Github
2. Download and unpack "ogs_maptool.zip"
3. Run the Executable

### Option 2:
1. Clone the repository
2. Download the necessary libraries by running "pip install -r requirements.txt" in your terminal, 
inside the project directory
3. Start project by running "python main.py"

## How to use the tool
### Land Image
The first tab takes a image that specifies the ocean area of the map,
the color defining the ocean must be RGB color (5,20,18), see example in the folder "example_input".
Everything else is considered land. 

### Boundary Image
The second tab defines the bounds that the provinces needs to adhere to.
Typical use would be borders for countries, states or other administrative units.
The boundery borders must be pure black, RGB (0,0,0), everything else will be ignored.

### Province Image
The third third tab generates the province map, based on the input in tab 1 and 2.
NB! You dont need both inputs, but you need at least one. 
Ex. A map without any ocean, does not need to have a input in tab 1, but then there must be a input in tab2, and visa versa.
Both input images must have the same dimensions/size for a good result.

Use the sliders to adjust the number of provinces on land and ocean.

Province map and the file containing province information(id,rgb,type,coordinates) can be exported after generation.

### Territory Image
The fourt tab generates the territory map, based on the generated provinces.
NB! You need to generate provinces before you can generate territories.

Use the sliders to adjust the number of territories on land and ocean.

Territory map and the file containing province information(id,rgb,type,coordinates) can be exported after generation.
Terriroity json files (One file per territory, defining the belonging provinces) can be exported after generation.

## Contributions
Contributions can come in many forms and all are appreciated:
- Feedback
- Code improvements
- Added functionality

## Discord 
Follow and/or support the project on [OpenGS Discord Server](https://discord.gg/6pRc9f6g6S)

## Delivered and maintained by 
<img width="350" height="350" alt="gsi-logo" src="https://github.com/user-attachments/assets/e7210566-7997-4d82-845e-48f249d439a0" />

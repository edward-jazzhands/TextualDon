# Third party imports
from bs4 import BeautifulSoup

# Textual imports
from textual.widget import Widget


class BS4Parser(Widget):


    def parser(self, html_content: str) -> str:
        
        soup =  BeautifulSoup(html_content, 'html.parser')

        #? notes/bs4_cheatsheet.md

        markdown_list = []
        markdown_str = ""

        for element in soup.find_all('br'):
            element.replace_with("\n")

        for element in soup.find_all('span', attrs={'class': 'invisible'}):
            element.decompose()

        for element in soup.find_all('span', attrs={'class': 'ellipsis'}):
            if element.string:
                element.string = element.string + "..."

        for element in soup.find_all('p'):        
            markdown_list.append(element.get_text(strip=False))       
            # markdown += f"{element.get_text(strip=True)}"

        # self.log.debug(markdown_list)

        # I believe this has to be separate from the second enumerate, because
        # the list is being modified while it loops. So it changes the index of items.
        # It might be possible to combine them into one loop, but it was giving me issues.
        # so fuck it, they're two loops.
        for index, element in enumerate(markdown_list):
            if element == "":
                markdown_list.pop(index)

        for index, element in enumerate(markdown_list):
            if index != len(markdown_list) - 1:     # if not last element,
                markdown_str += f"{element}\n\n"    # add 2 newlines
            else:
                markdown_str += f"{element}"        # last element does not get newlines


        return markdown_str
    


# EXAMPLE:

"""
<p>                                                                                                                                             
    Rocket Report: ULA 'supremely confident' in Vulcan; Impulse Space rakes it in                                                                  
</p>                                                                                                                                            
<p>                                                                                                                                             
    "I'm pretty darn confident I'm going to have a good day on Friday."                                                                          ▅▅
</p>                                                                                                                                            
<p>                                                                                                                                             
<a href="https://arstechnica.com/space/2024/10/rocket-report-ula-supremely-confident-in-vulcan-impulse-space-rakes-it-in/?utm_brand=arstechnica&amp;utm_social-type=owned&amp;utm_source=mastodon&amp;utm_medium=social" 
rel="nofollow noopener noreferrer" target="_blank" translate="no">                                                                              
<span class="invisible">                                                                                                                      
    https://                                                                                                                                     
</span>                                                                                                                                       
<span class="ellipsis">                                                                                                                       
    arstechnica.com/space/2024/10/                                                                                                               
</span>                                                                                                                                       
<span class="invisible">                                                                                                                      
    rocket-report-ula-supremely-confident-in-vulcan-impulse-space-rakes-it-in/?utm_brand=arstechnica&amp;utm_social-type=owned&amp;utm_source=mastodon&amp;utm_medium=social                                                                                 
</span>                                                                                                                                       
</a>                                                                                                                                           
</p>
"""
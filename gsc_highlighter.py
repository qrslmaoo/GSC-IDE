from PyQt6.Qsci import QsciLexerCPP
from PyQt6.QtGui import QColor, QFont


class GSCLexer(QsciLexerCPP):
    """Custom lexer for GSC syntax highlighting"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set dark theme colors
        self.setDefaultPaper(QColor("#1e1e1e"))
        self.setDefaultColor(QColor("#d4d4d4"))
        
        # Keywords (blue)
        self.setColor(QColor("#569cd6"), QsciLexerCPP.Keyword)
        
        # Comments (green)
        self.setColor(QColor("#57a64a"), QsciLexerCPP.Comment)
        self.setColor(QColor("#57a64a"), QsciLexerCPP.CommentLine)
        self.setColor(QColor("#57a64a"), QsciLexerCPP.CommentDoc)
        
        # Strings (orange)
        self.setColor(QColor("#ce9178"), QsciLexerCPP.DoubleQuotedString)
        self.setColor(QColor("#ce9178"), QsciLexerCPP.SingleQuotedString)
        
        # Numbers (light green)
        self.setColor(QColor("#b5cea8"), QsciLexerCPP.Number)
        
        # Operators (white)
        self.setColor(QColor("#d4d4d4"), QsciLexerCPP.Operator)
        
        # Preprocessor (purple)
        self.setColor(QColor("#c586c0"), QsciLexerCPP.PreProcessor)
    
    def keywords(self, set):
        """Define GSC keywords"""
        if set == 1:
            # Control flow keywords
            return " ".join([
                "if", "else", "for", "while", "do", "switch", "case", "default",
                "break", "continue", "return", "wait", "waittill", "endon",
                "notify", "thread", "true", "false", "undefined", "function"
            ])
        elif set == 2:
            # Built-in identifiers
            return " ".join([
                "self", "level", "game", "iprintln", "iprintlnbold", "setdvar",
                "getdvar", "precachemodel", "precacheshader", "spawn", "spawnstruct",
                "getent", "getentarray", "distance", "vectornormalize", "angles_to_forward",
                "playfx", "playsound", "playsoundatpos", "earthquake", "radiusdamage",
                "maps", "common_scripts", "utility"
            ])
        return ""

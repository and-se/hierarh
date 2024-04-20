{-# LANGUAGE OverloadedStrings #-}

module Main where

import Data.Aeson
import Data.Aeson.Encoding (pairs)
import Data.Aeson.Encode.Pretty
import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.ByteString.Lazy as BL
import System.Environment (getArgs)
import Text.XML
import Text.XML.Cursor
import Data.Maybe (listToMaybe)
import Control.Monad.IO.Class (liftIO)
import Control.Monad (forM)

-- Шаг 1: Определение структуры данных

data Person = Person
  { name :: Text
  , isRenovator :: Bool 
  , appointments :: [Appointment]
  } deriving Show

data Appointment = Appointment
  { department :: Text
  , dateRange :: Text
  } deriving Show

instance ToJSON Person where
  toJSON (Person name isRenovator appointments) =
    object ["name" .= name, "isRenovator" .= isRenovator, "appointments" .= appointments]

  toEncoding (Person name isRenovator appointments) =
    pairs ("name" .= name <> "isRenovator" .= isRenovator <> "appointments" .= appointments)

instance ToJSON Appointment where
  toJSON (Appointment department dateRange) =
    object ["department" .= department, "dates" .= dateRange]

  toEncoding (Appointment department dateRange) =
    pairs ("department" .= department <> "dates" .= dateRange)

-- Шаг 2: Разбор XML

parseDocument :: FilePath -> IO [Person]
parseDocument fp = do
  doc <- Text.XML.readFile def fp
  let cursor = fromDocument doc
  parsePeople cursor

parsePeople :: Cursor -> IO [Person]
parsePeople cursor = do
  let peopleCursors = cursor $// element "ParagraphStyleRange" 
                        >=> attributeStartsWith "AppliedParagraphStyle" "ParagraphStyle/Персона"
  liftIO $ putStrLn $ "Number of people: " ++ show (length peopleCursors)
  forM peopleCursors $ \personCursor -> do
    let name = T.strip . T.concat $ personCursor $// element "Content" &/ content
    let isRenovator = "Обновл" `T.isInfixOf` (T.concat $ attribute "AppliedParagraphStyle" personCursor)
    liftIO $ putStrLn $ "Found person: " ++ T.unpack name ++ (if isRenovator then " (Обновл)" else "")
    let appointmentCursor = takeWhile (not . isNextPerson) $ followingSibling personCursor
    appointments <- parseAppointments appointmentCursor
    return $ Person name isRenovator appointments

isNextPerson :: Cursor -> Bool
isNextPerson c = case attribute "AppliedParagraphStyle" c of
                    [] -> False
                    (val:_) -> "ParagraphStyle/Персона" `T.isPrefixOf` val

parseAppointments :: [Cursor] -> IO [Appointment]
parseAppointments cursors =  concatForM cursors $ \appointmentCursor -> do
      let contents = appointmentCursor $// element "CharacterStyleRange" &/ element "Content" &/ content
      forM (filter (not . T.null . T.strip) contents) $ \appointmentInfo -> do
        let (department, dateRange) = parseAppointmentInfo $ T.strip $ appointmentInfo
        liftIO $ putStrLn $ "Found appointment: " ++ T.unpack department ++ " - " ++ T.unpack dateRange
        return $ Appointment department dateRange

parseAppointmentInfo :: Text -> (Text, Text)
parseAppointmentInfo info = 
  let parts = T.splitOn "\t" info 
  in case parts of
       (dept:date) -> (dept, T.concat date)
       a -> ("unparsed", T.concat a) -- if error 

concatForM :: Monad m => [a] -> (a -> m [b]) -> m [b]
concatForM xs func = fmap concat $ forM xs func

attributeStartsWith :: Name -> Text -> Axis
attributeStartsWith name prefix = check $ \cursor -> 
    case attribute name cursor of
        [] -> False
        (attrVal:_) -> prefix `T.isPrefixOf` attrVal


-- Шаг 3: Главная функция и JSON конвертация

main :: IO ()
main = do
  args <- getArgs
  case args of
    [inputFileName, outputFileName] -> do
      people <- parseDocument inputFileName
      BL.writeFile outputFileName $ encodePretty people
    _ -> putStrLn "Usage: program <input.xml> <output.json>"



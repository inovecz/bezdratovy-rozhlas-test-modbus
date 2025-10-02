<?php

// device setting
$devicePort = '/dev/ttyUSB0';
$deviceBaud = 9600;

/**
 * komentar
 * - registr pro zacatek vysilani je 5035
 *              - 2 pro zacatek vysilani
 *              - 1 pro konec vysilani
 * 
 * - registry pro destinacni zony - 0x4030 - 0x4032
 *      - kazdy prijimac ma nastavenych nekolik adres, na ktere reaguje
 *          - nektere adresy jsou unikatni
 *          - nektere adresy lokality
 *          - nektere adresy, kdy nahrava do flashky
 *          - nektere adresy, kdy nahrava do flashky i prehrava
 *      - priklad: mam 3 hnizda s cilem 10, 11, 12
 *              - budu na nich chtit vysilat, tak v ten moment do registru
 * 
 * 
 * 
 * 
 * 
 * - adresa hnizda se nastavuje v SW
 *      - tedy oni to zadaji manualne do hnizda
 * 
 * - pokud budu chtit zacit vysilat
 *      1. nastavim destinace
 *          - to jsou ty destinacni zony
 *      2. zapnu vysilani - registr 5035 - posilam 2
 *      3. ukoncim vysilani - registr 5035 - posilam 1
 *  
 * 
 * pozn.
 * - pro komunikaci jsem zkusil python kod s RPi.GPIO
 * - je treba nastavit neparovy pin DE_RE_PIN 16
 * - musel jsem povolit seriovy port v raspberry configuration ??
 */




/**
 * registers
 * - 0x0000 - command/status
 * - 0x0001 - channel/track
 * - 0x0002 - volume optional
 * - 0x0003 - playback status
 * - 0x0004 - error code
 * - 0x0005 - duration
 * 
 * 
 * registers functions
 * - 01 - read coils (cte 1bitove vystupy - rele, led stav,...)
 * - 02 - read discrete inputs (cte 1bitove vstupy - tlacitka, binarni senzory,...)
 * - 03 - read holding registers (cte 16bitove vystupni registry)
 * - 04 - read inputs registers (cte 16bitove vstupni registry - teplota, napeti,...)
 * - 05 - write single coil (zapise 1bitovy vystup)
 * - 06 - write single register (zapise 16bitovy holding register) - nejcastejsi pro ovladani
 * - 0F - write multiple coils (zapis vice bitu - napr. 8led najednou)
 * - 10 - write multiple registers (zapis vice 16bit registru - napr. prikaz plus parametry najednou....)
 * 
 */



// Include Php Serial Modbus Class
require 'PhpSerialModbus.php';
$modbus = new PhpSerialModbus();

// Inicialize port
$modbus->deviceInit(
    $devicePort,
    $deviceBaud, 
    'none',                 // Parity
    8,                      // Char
    1,                      // Sbits
    'none');                // Flow

// Open connection
$modbus->deviceOpen();
$modbus->debug = false;


// Send query
$slaveId = 1;                   // pro prijimace je to 1, pro vysilace 55
$registerFunction = '03';       // 
$registerAddress = '0000';      // 
$registerValue = '0001';        // 
$result=$modbus->sendQuery(
    $slaveId,                  
    $registerFunction,     // Function code                  
    $registerAddress,      // Register address
    $registerValue,        // Value
    true,                  // If want to wait for response
    false);                 // If want to verify write




// Get response
$result=$modbus->getResponse(true);
print_r($result);

// Close connection
$modbus->deviceClose();
?>

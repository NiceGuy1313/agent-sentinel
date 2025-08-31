package guitracer

import "github.com/jezek/xgb/xproto"

type WindowAttributes struct {
	X                  int16
	Y                  int16
	Width              uint16
	Height             uint16
	BorderWidth        uint16
	Depth              byte
	visual             xproto.Visualid
	root               xproto.Window
	Class              uint16
	BitGravity         byte
	WinGravity         byte
	BackingStore       byte
	BackingPlanes      uint32
	BackingPixel       uint32
	SaveUnder          bool
	Colormap           xproto.Colormap
	MapIsInstalled     bool
	MapState           byte
	AllEventMasks      uint32
	YourEventMask      uint32
	DoNotPropagateMask uint16
	// TODO screens
}

type WindowLocation struct {
	X      int16
	Y      int16
	Width  uint16
	Height uint16
}

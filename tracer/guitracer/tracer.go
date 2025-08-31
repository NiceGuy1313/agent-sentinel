package guitracer

import (
	"github.com/jezek/xgb"
	"github.com/jezek/xgb/xproto"
	"github.com/rs/zerolog/log"
	"net"
)

type GUITracer struct {
	x11Conn *xgb.Conn
	setup   *xproto.SetupInfo
	root    xproto.Window
}

func NewGUITracer(addr string) (*GUITracer, error) {
	gt := &GUITracer{}
	if err := gt.connect(addr); err != nil {
		return nil, err
	}
	return gt, nil
}

func (gt *GUITracer) connect(addr string) error {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		log.Error().Err(err).Msgf("Connect to %s failed", addr)
		return err
	}

	if gt.x11Conn, err = xgb.NewConnNet(conn); err != nil {
		log.Error().Err(err).Msgf("Connect X11 server failed")
	}

	gt.setup = xproto.Setup(gt.x11Conn)
	gt.root = gt.setup.DefaultScreen(gt.x11Conn).Root
	return nil
}

func (gt *GUITracer) Close() {
	if gt.x11Conn != nil {
		gt.x11Conn.Close()
	}
}

func (gt *GUITracer) GetWindowLocationFromWindowID(windowId uint32, attr *WindowAttributes) (*WindowLocation, error) {
	if attr == nil {
		var err error
		attr, err = gt.GetWindowAttributesFromWindowID(windowId)
		if err != nil {
			return nil, err
		}
	}

	// use attr here ...

	treeReply, err := xproto.QueryTree(gt.x11Conn, xproto.Window(windowId)).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("XQueryTree failed")
		return nil, err
	}

	winLoc := &WindowLocation{
		Width:  attr.Width,
		Height: attr.Height,
	}
	if treeReply.Parent == gt.root {
		winLoc.X = attr.X
		winLoc.Y = attr.Y
	} else {
		tranReply, err := xproto.TranslateCoordinates(gt.x11Conn, treeReply.Root, xproto.Window(windowId), attr.X, attr.Y).Reply()
		if err != nil {
			log.Error().Err(err).Msgf("XTranslateCoordinates failed")
			return nil, err
		}

		winLoc.X = tranReply.DstX
		winLoc.Y = tranReply.DstY
	}

	log.Debug().Msgf("GetWindowLocationFromWindowID: %+v", winLoc)

	return winLoc, nil
}

func (gt *GUITracer) GetWindowAttributesFromWindowID(windowId uint32) (*WindowAttributes, error) {
	waReply, err := xproto.GetWindowAttributes(gt.x11Conn, xproto.Window(windowId)).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("XGetWindowAttributes failed")
		return nil, err
	}

	gemReply, err := xproto.GetGeometry(gt.x11Conn, xproto.Drawable(windowId)).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("XGetGeometry failed")
		return nil, err
	}

	wa := &WindowAttributes{
		X:                  gemReply.X,
		Y:                  gemReply.Y,
		BorderWidth:        gemReply.BorderWidth,
		Width:              gemReply.Width,
		Height:             gemReply.Height,
		Depth:              gemReply.Depth,
		visual:             waReply.Visual,
		Class:              waReply.Class,
		BitGravity:         waReply.BitGravity,
		WinGravity:         waReply.WinGravity,
		BackingStore:       waReply.BackingStore,
		BackingPlanes:      waReply.BackingPlanes,
		BackingPixel:       waReply.BackingPixel,
		SaveUnder:          waReply.SaveUnder,
		Colormap:           waReply.Colormap,
		MapIsInstalled:     waReply.MapIsInstalled,
		MapState:           waReply.MapState,
		AllEventMasks:      waReply.AllEventMasks,
		YourEventMask:      waReply.YourEventMask,
		DoNotPropagateMask: waReply.DoNotPropagateMask,
	}
	log.Debug().Msgf("GetWindowAttributes: %#v", wa)
	return wa, nil
}

func (gt *GUITracer) GetWindowStack() ([]uint32, error) {
	aname := "_NET_CLIENT_LIST_STACKING"
	windowStack, err := xproto.InternAtom(gt.x11Conn, true, uint16(len(aname)), aname).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get _NET_CLIENT_LIST_STACKING failed")
		return nil, err
	}

	reply, err := xproto.GetProperty(gt.x11Conn, false, gt.root, windowStack.Atom,
		xproto.GetPropertyTypeAny, 0, (1<<32)-1).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get active window id failed")
		return nil, err
	}

	depth := len(reply.Value) / 4
	wstack := make([]uint32, depth)
	for i := 0; i < depth; i++ {
		wstack[i] = xgb.Get32(reply.Value[i*4 : (i+1)*4])
	}

	// fmt.Printf("xxx: %v\n", wstack)
	return wstack, nil
}

func (gt *GUITracer) GetActiveWindowID() (uint32, error) {
	// Get the atom id (i.e., intern an atom) of "_NET_ACTIVE_WINDOW".
	aname := "_NET_ACTIVE_WINDOW"
	activeAtom, err := xproto.InternAtom(gt.x11Conn, true, uint16(len(aname)),
		aname).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get _NET_ACTIVE_WINDOW failed")
		return 0, err
	}

	// Get the actual value of _NET_ACTIVE_WINDOW.
	// Note that 'reply.Value' is just a slice of bytes, so we use an
	// XGB helper function, 'Get32', to pull an unsigned 32-bit integer out
	// of the byte slice. We then convert it to an X resource id so it can
	// be used to get the name of the window in the next GetProperty request.
	reply, err := xproto.GetProperty(gt.x11Conn, false, gt.root, activeAtom.Atom,
		xproto.GetPropertyTypeAny, 0, (1<<32)-1).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get active window id failed")
		return 0, err
	}

	wid := xgb.Get32(reply.Value)
	// TODO {type:..., data: ...}
	log.Debug().Msgf("Active window id: %X\n", wid)
	return wid, nil
}

func (gt *GUITracer) GetWindowName(windowId uint32) (string, error) {
	// Get the atom id (i.e., intern an atom) of "_NET_WM_NAME".
	aname := "_NET_WM_NAME"
	nameAtom, err := xproto.InternAtom(gt.x11Conn, true, uint16(len(aname)),
		aname).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get _NET_ACTIVE_WINDOW failed")
		return "", err
	}

	// Now get the value of _NET_WM_NAME for the active window.
	// Note that this time, we simply convert the resulting byte slice,
	// reply.Value, to a string.
	reply, err := xproto.GetProperty(gt.x11Conn, false, xproto.Window(windowId), nameAtom.Atom,
		xproto.GetPropertyTypeAny, 0, (1<<32)-1).Reply()
	if err != nil {
		log.Error().Err(err).Msgf("Get active window name failed")
		return "", err
	}
	log.Debug().Msgf("Active window name: %s\n", string(reply.Value))

	return string(reply.Value), nil
}

package helper

import (
	"bytes"
	"regexp"
	"strings"
)

func CompileFilePattern(pattern string) (*regexp.Regexp, error) {
	patternSegs := strings.Split(pattern, "/")

	if patternSegs[0] == "" {
		// remove the empty segment if a pattern begins with a slash `/`
		patternSegs = patternSegs[1:]
	} else if patternSegs[0] != "**" {
		// a pattern without a beginning slash ('/') will match any
		// descendant path. This is equivalent to "**/{pattern}".
		patternSegs = append([]string{"**"}, patternSegs...)
	}

	if patternSegs[len(patternSegs)-1] == "" {
		// A pattern ending with a slash ('/') will match all descendant paths
		// This is equivalent to "{pattern}/**"
		patternSegs[len(patternSegs)-1] = "**"
	}

	var expr bytes.Buffer
	expr.WriteString("^")
	needSlash := false

	for i, seg := range patternSegs {
		switch seg {
		case "**":
			switch {
			case i == 0 && i == len(patternSegs)-1:
				// A pattern consisting solely of double-asterisks ('**')
				// will match every path.
				expr.WriteString(".+")
			case i == 0:
				// A normalized pattern beginning with double-asterisks
				// ('**') will match any leading path segments.
				expr.WriteString("(?:.+/)?")
				needSlash = false
			case i == len(patternSegs)-1:
				// A normalized pattern ending with double-asterisks ('**')
				// will match any trailing path segments.
				expr.WriteString("/.+")
			default:
				// A pattern with inner double-asterisks ('**') will match
				// multiple (or zero) inner path segments.
				expr.WriteString("(?:/.+)?")
				needSlash = true
			}
		case "*":
			// Match single path segment.
			if needSlash {
				expr.WriteString("/")
			}
			expr.WriteString("[^/]+")
			needSlash = true
		default:
			// Match segment glob pattern.
			if needSlash || i == 0 {
				expr.WriteString("/")
			}

			expr.WriteString(seg)

			// TODO: support standard glob path pattern
			// expr.WriteString(translateGlob(seg))
			needSlash = true
		}
	}
	expr.WriteString("$")
	// log.Debug().Str("pattern", expr.String()).Msg("compiling pattern")
	reg, err := regexp.Compile(expr.String())

	if err != nil {
		return nil, err
	}

	return reg, nil
}

// NOTE: This is derived from `fnmatch.translate()` and is similar to
// the POSIX function `fnmatch()` with the `FNM_PATHNAME` flag set.
//func translateGlob(glob string) string {
//	var regex bytes.Buffer
//	escape := false
//
//	for i := 0; i < len(glob); i++ {
//		char := glob[i]
//		// Escape the character.
//		switch {
//		case escape:
//			escape = false
//			regex.WriteString(regexp.QuoteMeta(string(char)))
//		case char == '\\':
//			// Escape character, escape next character.
//			escape = true
//		case char == '*':
//			// Multi-character wildcard. Match any string (except slashes),
//			// including an empty string.
//			regex.WriteString("[^/]*")
//		case char == '?':
//			// Single-character wildcard. Match any single character (except
//			// a slash).
//			regex.WriteString("[^/]")
//		case char == '[':
//			regex.WriteString(translateBraketExpression(&i, glob))
//		default:
//			// Regular character, escape it for regex.
//			regex.WriteString(regexp.QuoteMeta(string(char)))
//		}
//	}
//	return regex.String()
//}
//
//// Braket expression wildcard. Except for the beginning
//// exclamation mark, the whole braket expression can be used
//// directly as regex but we have to find where the expression
//// ends.
//// - "[][!]" matchs ']', '[' and '!'.
//// - "[]-]" matchs ']' and '-'.
//// - "[!]a-]" matchs any character except ']', 'a' and '-'.
//func translateBraketExpression(i *int, glob string) string {
//	regex := string(glob[*i])
//	*i++
//	j := *i
//
//	// Pass brack expression negation.
//	if j < len(glob) && glob[j] == '!' {
//		j++
//	}
//	// Pass first closing braket if it is at the beginning of the
//	// expression.
//	if j < len(glob) && glob[j] == ']' {
//		j++
//	}
//	// Find closing braket. Stop once we reach the end or find it.
//	for j < len(glob) && glob[j] != ']' {
//		j++
//	}
//
//	if j < len(glob) {
//		if glob[*i] == '!' {
//			regex = regex + "^"
//			*i++
//		}
//		regex = regexp.QuoteMeta(glob[*i:j])
//		*i = j
//	} else {
//		// Failed to find closing braket, treat opening braket as a
//		// braket literal instead of as an expression.
//		regex = regexp.QuoteMeta(string(glob[*i]))
//	}
//	return "[" + regex + "]"
//}

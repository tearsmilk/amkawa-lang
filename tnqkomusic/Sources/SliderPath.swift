import CoreGraphics
import Foundation

/// Ломаная слайдера: L — отрезки, P — дуга окружности по трём точкам, B — Безье с «красными» узлами, C — Catmull-Rom.
final class SliderPath {
    let points: [CGPoint]
    let cumulative: [Double]
    var length: Double { cumulative.last ?? 0 }

    init(type: Character, control: [CGPoint], pixelLength: Double) {
        var poly: [CGPoint]
        switch type {
        case "L": poly = control
        case "P": poly = (control.count == 3 ? SliderPath.arc(control) : nil) ?? SliderPath.bezier(control)
        case "C": poly = SliderPath.catmull(control)
        default: poly = SliderPath.bezier(control)
        }
        var clean: [CGPoint] = []
        for p in poly where clean.last.map({ hypot($0.x - p.x, $0.y - p.y) > 0.01 }) ?? true { clean.append(p) }
        if clean.isEmpty { clean = [control.first ?? .zero] }

        var cum: [Double] = [0]
        for i in 1..<max(1, clean.count) {
            cum.append(cum[i - 1] + Double(hypot(clean[i].x - clean[i - 1].x, clean[i].y - clean[i - 1].y)))
        }
        let full = cum.last ?? 0
        let target = pixelLength > 0 ? pixelLength : full

        if target < full {
            // обрезаем до заявленной длины
            var pts = [clean[0]]
            var c = [0.0]
            for i in 1..<clean.count {
                if cum[i] >= target {
                    let seg = cum[i] - cum[i - 1]
                    let f = seg > 0 ? (target - cum[i - 1]) / seg : 0
                    let a = clean[i - 1], b = clean[i]
                    pts.append(CGPoint(x: a.x + (b.x - a.x) * CGFloat(f), y: a.y + (b.y - a.y) * CGFloat(f)))
                    c.append(target)
                    break
                }
                pts.append(clean[i])
                c.append(cum[i])
            }
            points = pts
            cumulative = c
        } else if target > full + 0.01 {
            // продлеваем последний отрезок по направлению
            var pts = clean
            var c = cum
            let last = clean[clean.count - 1]
            let prev = clean.count > 1 ? clean[clean.count - 2] : CGPoint(x: last.x - 1, y: last.y)
            let len = max(0.0001, Double(hypot(last.x - prev.x, last.y - prev.y)))
            let extra = target - full
            pts.append(CGPoint(x: last.x + CGFloat(Double(last.x - prev.x) / len * extra), y: last.y + CGFloat(Double(last.y - prev.y) / len * extra)))
            c.append(target)
            points = pts
            cumulative = c
        } else {
            points = clean
            cumulative = cum
        }
    }

    /// Точка на доле пути 0…1.
    func point(at progress: Double) -> CGPoint {
        guard points.count > 1, length > 0 else { return points.first ?? .zero }
        let d = max(0, min(1, progress)) * length
        var lo = 0, hi = cumulative.count - 1
        while lo < hi - 1 {
            let mid = (lo + hi) / 2
            if cumulative[mid] < d { lo = mid } else { hi = mid }
        }
        let seg = cumulative[hi] - cumulative[lo]
        let f = seg > 0 ? CGFloat((d - cumulative[lo]) / seg) : 0
        let a = points[lo], b = points[hi]
        return CGPoint(x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f)
    }

    static func arc(_ p: [CGPoint]) -> [CGPoint]? {
        let a = p[0], b = p[1], c = p[2]
        let d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
        if abs(d) < 0.001 { return nil }
        let a2 = a.x * a.x + a.y * a.y, b2 = b.x * b.x + b.y * b.y, c2 = c.x * c.x + c.y * c.y
        let center = CGPoint(x: (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d,
                             y: (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d)
        let r = Double(hypot(a.x - center.x, a.y - center.y))
        let start = atan2(Double(a.y - center.y), Double(a.x - center.x))
        var end = atan2(Double(c.y - center.y), Double(c.x - center.x))
        // направление: по знаку векторного произведения (a→b)×(b→c)
        let cross = Double((b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x))
        if cross > 0 {
            while end < start { end += 2 * .pi }
        } else {
            while end > start { end -= 2 * .pi }
        }
        let steps = max(8, Int(abs(end - start) * r / 4))
        return (0...steps).map { i in
            let t = start + (end - start) * Double(i) / Double(steps)
            return CGPoint(x: center.x + CGFloat(cos(t) * r), y: center.y + CGFloat(sin(t) * r))
        }
    }

    static func bezier(_ control: [CGPoint]) -> [CGPoint] {
        var out: [CGPoint] = []
        var segment: [CGPoint] = []
        func flush() {
            guard !segment.isEmpty else { return }
            if segment.count < 3 {
                out.append(contentsOf: segment)
            } else {
                var approx = 0.0
                for i in 1..<segment.count { approx += Double(hypot(segment[i].x - segment[i - 1].x, segment[i].y - segment[i - 1].y)) }
                let steps = max(8, min(400, Int(approx / 3)))
                for s in 0...steps { out.append(casteljau(segment, Double(s) / Double(steps))) }
            }
        }
        for (i, p) in control.enumerated() {
            segment.append(p)
            // повтор точки = «красный» узел: конец одного сегмента и начало следующего
            if i + 1 < control.count, control[i + 1] == p {
                flush()
                segment = []
            }
        }
        flush()
        return out
    }

    static func casteljau(_ pts: [CGPoint], _ t: Double) -> CGPoint {
        var p = pts
        let tt = CGFloat(t)
        while p.count > 1 {
            for i in 0..<(p.count - 1) { p[i] = CGPoint(x: p[i].x + (p[i + 1].x - p[i].x) * tt, y: p[i].y + (p[i + 1].y - p[i].y) * tt) }
            p.removeLast()
        }
        return p[0]
    }

    static func catmull(_ p: [CGPoint]) -> [CGPoint] {
        guard p.count > 1 else { return p }
        var out: [CGPoint] = []
        for i in 0..<(p.count - 1) {
            let v1 = i > 0 ? p[i - 1] : p[i]
            let v2 = p[i], v3 = p[i + 1]
            let v4 = i + 2 < p.count ? p[i + 2] : CGPoint(x: 2 * v3.x - v2.x, y: 2 * v3.y - v2.y)
            for s in 0...50 {
                let t = CGFloat(s) / 50, t2 = t * t, t3 = t2 * t
                func c(_ a: CGFloat, _ b: CGFloat, _ cc: CGFloat, _ d: CGFloat) -> CGFloat {
                    0.5 * (2 * b + (-a + cc) * t + (2 * a - 5 * b + 4 * cc - d) * t2 + (-a + 3 * b - 3 * cc + d) * t3)
                }
                out.append(CGPoint(x: c(v1.x, v2.x, v3.x, v4.x), y: c(v1.y, v2.y, v3.y, v4.y)))
            }
        }
        return out
    }
}

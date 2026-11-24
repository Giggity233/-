param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,

    [Parameter(Mandatory = $true)]
    [string]$OutputFile
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$source = [System.Drawing.Image]::FromFile($InputFile)
try {
    $images = @()
    foreach ($size in 16, 24, 32, 48, 64, 128, 256) {
        $bitmap = [System.Drawing.Bitmap]::new($size, $size)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $scale = [Math]::Min($size / $source.Width, $size / $source.Height)
                $width = [Math]::Round($source.Width * $scale)
                $height = [Math]::Round($source.Height * $scale)
                $x = [Math]::Round(($size - $width) / 2)
                $y = [Math]::Round(($size - $height) / 2)
                $graphics.DrawImage($source, $x, $y, $width, $height)
            }
            finally {
                $graphics.Dispose()
            }

            $png = [System.IO.MemoryStream]::new()
            try {
                $bitmap.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
                $images += [pscustomobject]@{ Size = $size; Bytes = $png.ToArray() }
            }
            finally {
                $png.Dispose()
            }
        }
        finally {
            $bitmap.Dispose()
        }
    }
}
finally {
    $source.Dispose()
}

$stream = [System.IO.MemoryStream]::new()
$writer = [System.IO.BinaryWriter]::new($stream)
try {
    $writer.Write([uint16]0) # reserved
    $writer.Write([uint16]1) # ICO
    $writer.Write([uint16]$images.Count)
    $offset = 6 + (16 * $images.Count)
    foreach ($image in $images) {
        $dimension = if ($image.Size -eq 256) { [byte]0 } else { [byte]$image.Size }
        $writer.Write($dimension)
        $writer.Write($dimension)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([uint16]1)
        $writer.Write([uint16]32)
        $writer.Write([uint32]$image.Bytes.Length)
        $writer.Write([uint32]$offset)
        $offset += $image.Bytes.Length
    }
    foreach ($image in $images) {
        $writer.Write($image.Bytes)
    }
    [System.IO.File]::WriteAllBytes($OutputFile, $stream.ToArray())
}
finally {
    $writer.Dispose()
    $stream.Dispose()
}

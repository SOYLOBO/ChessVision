import AVFoundation
import UIKit

enum CameraLens: String, CaseIterable, Identifiable {
  case ultraWide = "0.5x"
  case wide = "1x"
  case telephoto = "2x"
  case telephoto3x = "3x"
  case telephoto5x = "5x"

  var id: String { rawValue }

  var deviceType: AVCaptureDevice.DeviceType {
    switch self {
    case .ultraWide: return .builtInUltraWideCamera
    case .wide: return .builtInWideAngleCamera
    case .telephoto, .telephoto3x, .telephoto5x: return .builtInTelephotoCamera
    }
  }

  static func available() -> [CameraLens] {
    let discovery = AVCaptureDevice.DiscoverySession(
      deviceTypes: [.builtInUltraWideCamera, .builtInWideAngleCamera, .builtInTelephotoCamera],
      mediaType: .video,
      position: .back
    )
    let deviceTypes = Set(discovery.devices.map { $0.deviceType })
    var lenses: [CameraLens] = []
    if deviceTypes.contains(.builtInUltraWideCamera) { lenses.append(.ultraWide) }
    if deviceTypes.contains(.builtInWideAngleCamera) { lenses.append(.wide) }
    if deviceTypes.contains(.builtInTelephotoCamera) {
      if let tele = discovery.devices.first(where: { $0.deviceType == .builtInTelephotoCamera }) {
        let zoom = tele.maxAvailableVideoZoomFactor
        if zoom >= 5 { lenses.append(.telephoto5x) }
        else if zoom >= 3 { lenses.append(.telephoto3x) }
        else { lenses.append(.telephoto) }
      }
    }
    return lenses
  }
}

class IPhoneCameraManager: NSObject {
  private let captureSession = AVCaptureSession()
  private let videoOutput = AVCaptureVideoDataOutput()
  private let sessionQueue = DispatchQueue(label: "iphone-camera-session")
  private let context = CIContext()
  private var isRunning = false
  private var currentDevice: AVCaptureDevice?
  private(set) var currentLens: CameraLens = .wide

  var onFrameCaptured: ((UIImage) -> Void)?

  func switchLens(_ lens: CameraLens) {
    sessionQueue.async { [weak self] in
      guard let self, self.isRunning else { return }
      guard let device = AVCaptureDevice.default(lens.deviceType, for: .video, position: .back),
            let newInput = try? AVCaptureDeviceInput(device: device) else {
        NSLog("[iPhoneCamera] Lens %@ not available", lens.rawValue)
        return
      }
      self.captureSession.beginConfiguration()
      if let currentInput = self.captureSession.inputs.first as? AVCaptureDeviceInput {
        self.captureSession.removeInput(currentInput)
      }
      if self.captureSession.canAddInput(newInput) {
        self.captureSession.addInput(newInput)
        self.currentDevice = device
        self.currentLens = lens
        do {
          try device.lockForConfiguration()
          if device.isFocusModeSupported(.continuousAutoFocus) {
            device.focusMode = .continuousAutoFocus
          }
          if device.isExposureModeSupported(.continuousAutoExposure) {
            device.exposureMode = .continuousAutoExposure
          }
          device.unlockForConfiguration()
        } catch {}
      }
      if let connection = self.videoOutput.connection(with: .video),
         connection.isVideoRotationAngleSupported(90) {
        connection.videoRotationAngle = 90
      }
      self.captureSession.commitConfiguration()
      NSLog("[iPhoneCamera] Switched to %@ lens", lens.rawValue)
    }
  }

  func focusAt(point: CGPoint) {
    guard let device = currentDevice else { return }
    sessionQueue.async {
      do {
        try device.lockForConfiguration()
        if device.isFocusPointOfInterestSupported {
          device.focusPointOfInterest = point
          device.focusMode = .autoFocus
        }
        if device.isExposurePointOfInterestSupported {
          device.exposurePointOfInterest = point
          device.exposureMode = .autoExpose
        }
        device.unlockForConfiguration()
      } catch {
        NSLog("[iPhoneCamera] Focus error: %@", error.localizedDescription)
      }
    }
  }

  func start() {
    guard !isRunning else { return }
    sessionQueue.async { [weak self] in
      self?.configureSession()
      self?.captureSession.startRunning()
      self?.isRunning = true
    }
  }

  func stop() {
    guard isRunning else { return }
    sessionQueue.async { [weak self] in
      self?.captureSession.stopRunning()
      self?.isRunning = false
    }
  }

  private func configureSession() {
    captureSession.beginConfiguration()
    captureSession.sessionPreset = .photo

    // Add back camera input
    guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
          let input = try? AVCaptureDeviceInput(device: camera) else {
      NSLog("[iPhoneCamera] Failed to access back camera")
      captureSession.commitConfiguration()
      return
    }
    currentDevice = camera

    do {
      try camera.lockForConfiguration()
      if camera.isFocusModeSupported(.continuousAutoFocus) {
        camera.focusMode = .continuousAutoFocus
      }
      if camera.isExposureModeSupported(.continuousAutoExposure) {
        camera.exposureMode = .continuousAutoExposure
      }
      camera.unlockForConfiguration()
    } catch {
      NSLog("[iPhoneCamera] Config error: %@", error.localizedDescription)
    }

    if captureSession.canAddInput(input) {
      captureSession.addInput(input)
    }

    // Add video output
    videoOutput.videoSettings = [
      kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
    ]
    videoOutput.setSampleBufferDelegate(self, queue: sessionQueue)
    videoOutput.alwaysDiscardsLateVideoFrames = true

    if captureSession.canAddOutput(videoOutput) {
      captureSession.addOutput(videoOutput)
    }

    // Force portrait-oriented frames from the sensor
    if let connection = videoOutput.connection(with: .video) {
      if connection.isVideoRotationAngleSupported(90) {
        connection.videoRotationAngle = 90
      }
    }

    captureSession.commitConfiguration()
    NSLog("[iPhoneCamera] Session configured")
  }

  static func requestPermission() async -> Bool {
    let status = AVCaptureDevice.authorizationStatus(for: .video)
    switch status {
    case .authorized:
      return true
    case .notDetermined:
      return await AVCaptureDevice.requestAccess(for: .video)
    default:
      return false
    }
  }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate

extension IPhoneCameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
  func captureOutput(
    _ output: AVCaptureOutput,
    didOutput sampleBuffer: CMSampleBuffer,
    from connection: AVCaptureConnection
  ) {
    guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

    let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
    guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else { return }
    let image = UIImage(cgImage: cgImage)

    onFrameCaptured?(image)
  }
}
